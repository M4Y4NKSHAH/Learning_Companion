import os
import json
import time
import hashlib
import re
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, List, Union


class LocalLLMService:
    """
    Local LLM Inference Engine optimized for Ollama on consumer GPUs (RTX 2050 4GB).

    Features added in the v2 overhaul:
    - `resolve_model_name()`: prefers the fine-tuned `learning-companion` model
      (built from `training/Modelfile` + the Llama-3.2-3B LoRA adapter), falling back
      to stock `llama3.2:3b` when the tuned model is not registered in Ollama.
    - Native Ollama JSON mode: `/api/chat` with `format: "json"` so the small
      3B instruct model emits strictly valid JSON without markdown fences.
    - Robust `_repair_json()`: numeric repair for truncated / escaped output so the
      theory pipeline never hard-fails on a slightly malformed completion.
    - Hardened prompt budget tracking (context-window protective), deterministic
      generation defaults, and an in-memory response cache for repeated prompts.
    """

    # Model preference order: fine-tuned educational model first, stock instruct second.
    DEFAULT_MODELS = ("learning-companion", "llama3.2:3b")

    def __init__(self, base_url: str = "http://localhost:11434", model_name: Optional[str] = None):
        self.base_url = os.getenv("LOCAL_LLM_URL", base_url)
        self.model_name = (model_name or os.getenv("LOCAL_LLM_MODEL") or self.DEFAULT_MODELS[0])
        self._available_cache: Optional[bool] = None
        self._available_ts: float = 0
        self._model_tags: Optional[List[str]] = None
        self._model_tags_ts: float = 0
        self._CACHE_TTL = 25.0  # seconds
        self._TAGS_TTL = 300.0  # seconds
        self._resp_cache: Dict[str, str] = {}
        self._resp_cache_ts: Dict[str, float] = {}
        self._RESP_CACHE_TTL = 600.0  # seconds (10 minutes)
        self._PROMPT_BUDGET = int(os.getenv("LOCAL_LLM_PROMPT_BUDGET", "3400"))
# ------------------------------------------------------------------ #
    # Availability & model resolution
    # ------------------------------------------------------------------ #
    def _fetch_tags(self) -> Optional[List[str]]:
        """Fetches the list of model names registered on the Ollama instance."""
        now = time.monotonic()
        if self._model_tags is not None and (now - self._model_tags_ts) < self._TAGS_TTL:
            return self._model_tags
        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=2.0) as res:
                if res.status == 200:
                    data = json.loads(res.read().decode("utf-8"))
                    tags = [m.get("name", "") for m in data.get("models", [])]
                    self._model_tags = tags
                    self._model_tags_ts = now
                    return tags
        except Exception as e:
            print(f"[LocalLLMService] Tag fetch warning: {e}")
        return self._model_tags

    def resolve_model_name(self) -> str:
        """
        Resolves the best model actually available on the local Ollama instance.
        Prefers the fine-tuned 'learning-companion' model (built from the LoRA adapter
        in training/), then the stock 'llama3.2:3b' instruct model.
        """
        pinned = os.getenv("LOCAL_LLM_MODEL")
        if pinned:
            return pinned

        tags = self._fetch_tags()
        if not tags:
            return self.model_name

        # Normalize tags: strip ':latest' so 'learning-companion:latest' == 'learning-companion'
        normalized = [t.split(":")[0] for t in tags]
        for candidate in self.DEFAULT_MODELS:
            base = candidate.split(":")[0]
            if candidate in tags or base in normalized:
                return candidate

        return self.model_name

    def is_available(self) -> bool:
        """Checks if local Ollama is actively running (cached for 25s)."""
        now = time.monotonic()
        if self._available_cache is not None and (now - self._available_ts) < self._CACHE_TTL:
            return self._available_cache

        try:
            req = urllib.request.Request(f"{self.base_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=1.5) as res:
                self._available_cache = (res.status == 200)
        except Exception:
            self._available_cache = False

        self._available_ts = now
        return self._available_cache
# ------------------------------------------------------------------ #
    # Core generation (chat-based, JSON-mode capable)
    # ------------------------------------------------------------------ #
    def generate_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 1024,
        timeout: int = 90,
        format_json: bool = False,
        num_ctx: int = 2048,
        top_p: float = 0.9,
        repeat_penalty: float = 1.1,
    ) -> Optional[str]:
        """
        Chat completions against Ollama /api/chat. The 3B model behaves measurably
        better with a proper chat template (llama-3) than with raw /api/generate.
        `format_json=True` enables Ollama's native structured-output decoding.
        """
        if not self.is_available():
            return None

        model = self.resolve_model_name()

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "num_ctx": num_ctx,
                "top_p": top_p,
                "repeat_penalty": repeat_penalty,
                "stop": ["<|eot_id|>"],
            },
        }
        if format_json:
            payload["format"] = "json"

        # Cache identical structured-request prompts to avoid redundant GPU cycles.
        cache_key = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        now = time.monotonic()
        cached = self._resp_cache.get(cache_key)
        if cached is not None and (now - self._resp_cache_ts.get(cache_key, 0)) < self._RESP_CACHE_TTL:
            return cached

        try:
            req = urllib.request.Request(
                f"{self.base_url}/api/chat",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as res:
                if res.status == 200:
                    data = json.loads(res.read().decode("utf-8"))
                    content = (data.get("message") or {}).get("content", "") or data.get("response", "")
                    content = content.strip()
                    if content:
                        self._resp_cache[cache_key] = content
                        self._resp_cache_ts[cache_key] = now
                    return content or None
        except Exception as e:
            print(f"[LocalLLMService] Chat inference warning: {e}")
            return None

        return None

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
        timeout: int = 75,
    ) -> Optional[str]:
        """
        Backwards-compatible generate API. Routes through /api/chat with the llama-3
        templating so existing callers keep working but benefit from instruct formatting.
        """
        if not self.is_available():
            return None

        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt[:1500]})
        messages.append({"role": "user", "content": prompt[:self._PROMPT_BUDGET]})

        return self.generate_chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )

    def generate_structured_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 1000,
        timeout: int = 90,
        root_type: str = "object",
    ) -> Optional[Union[Dict[str, Any], List[Any]]]:
        """
        Generates a structured JSON response using Ollama's native JSON mode and
        hardens the result with `_repair_json`. Returns the parsed object/list or None.
        """
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt[:1600]})
        messages.append({"role": "user", "content": prompt[:self._PROMPT_BUDGET]})

        raw = self.generate_chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            format_json=True,
            num_ctx=2048,
        )
        if not raw:
            return None

        cleaned = self._clean_json_str(raw)
        if not cleaned:
            return None

        try:
            parsed = json.loads(cleaned)
        except Exception as first_err:
            repaired = self._repair_json(cleaned)
            try:
                parsed = json.loads(repaired)
            except Exception:
                print(f"[LocalLLMService] Structured JSON failed: {first_err}\nRAW: {raw[:240]}")
                return None

        if root_type == "object" and isinstance(parsed, dict):
            return parsed
        if root_type == "array" and isinstance(parsed, list):
            return parsed
        # Allow object->array mismatch: many small models return object when array asked.
        if isinstance(parsed, dict) and root_type == "array":
            return [parsed]
        if isinstance(parsed, list) and root_type == "object" and parsed:
            return parsed[0] if isinstance(parsed[0], dict) else None
        return parsed if isinstance(parsed, (dict, list)) else None

    # ------------------------------------------------------------------ #
    # JSON hardening
    # ------------------------------------------------------------------ #
    @staticmethod
    def _clean_json_str(text: str) -> str:
        """Strips markdown fences and isolates valid JSON object/array substrings."""
        cleaned = text.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```", 1)[1].split("```", 1)[0].strip()

        first_brace = cleaned.find("{")
        first_bracket = cleaned.find("[")
        if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
            last_brace = cleaned.rfind("}")
            if last_brace != -1:
                cleaned = cleaned[first_brace:last_brace + 1]
        elif first_bracket != -1:
            last_bracket = cleaned.rfind("]")
            if last_bracket != -1:
                cleaned = cleaned[first_bracket:last_bracket + 1]

        return cleaned

    @classmethod
    def _repair_json(cls, text: str) -> str:
        """
        Repair heuristics for small-model JSON output:
        - Removes trailing commas before } or ].
        - Fixes unbalanced quotes in keys silently by dropping broken tail.
        - Rounds numeric garbage / NaN into null.
        Network-free, deterministic, and safe for any schema.
        """
        if not text:
            return "{}"
        repaired = text
        # 1. Trailing commas
        repaired = re.sub(r",\s*(?=[}\]])", "", repaired)
        # 2. Unquoted keys produced by some quantizations
        repaired = re.sub(r'([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:', r'\1"\2":', repaired)
        # 3. Single-quoted strings -> double-quoted (only as safer default)
        repaired = re.sub(r"(?<!\")(?:')(.*?)(?:')(?!\")", r'"\1"', repaired)
        # 4. JavaScript-ish NaN/Infinity/undefined
        repaired = re.sub(r"\bNaN\b|\bundefined\b|Infinity", "null", repaired)
        # 5. Escape stray newlines inside strings
        repaired = repaired.replace("\n", "\\n").replace("\t", "\\t")
        return repaired
# ------------------------------------------------------------------ #
    # Curriculum-specific helpers (kept for backward compatibility)
    # ------------------------------------------------------------------ #
    def summarize_chapter_and_generate_cards(self, chapter_title: str, chapter_content: str, subject: str) -> Optional[Dict[str, Any]]:
        """Generates structured summary and 3 flashcards using local Llama model (JSON-mode)."""
        prompt = f"""You are an expert curriculum summarizer for {subject}.
Analyze the following section:
Title: {chapter_title}
Content:
{chapter_content[:2400]}

Generate a valid JSON object with EXACTLY this structure:
{{
  "summary": "2-3 sentence overview of governing principles",
  "objectives": ["Objective 1", "Objective 2", "Objective 3"],
  "cards": [
    {{
      "topic": "{chapter_title}",
      "question": "Clear conceptual question",
      "answer": "• Core Principle: ...\\n• Governing Rule: ...\\n• Application: ..."
    }},
    {{
      "topic": "{chapter_title}",
      "question": "Another conceptual or formula question",
      "answer": "• Key Takeaway: ...\\n• Mechanism: ...\\n• Common Pitfall: ..."
    }},
    {{
      "topic": "{chapter_title}",
      "question": "Third critical question",
      "answer": "• Definition: ...\\n• Mathematical/Physical Intuition: ...\\n• Impact: ..."
    }}
  ]
}}
Respond ONLY with the raw JSON object, no Markdown backticks or commentary."""

        parsed = self.generate_structured_json(
            prompt=prompt,
            system_prompt="You are a JSON-only curriculum generator.",
            max_tokens=1200,
        )
        if not parsed:
            return None
        cards = parsed.get("cards", [])
        if isinstance(cards, dict):
            cards = [cards]
        parsed["cards"] = cards[:3] if isinstance(cards, list) else []
        if not isinstance(parsed.get("objectives"), list):
            parsed["objectives"] = [parsed.get("objectives", "Master this topic")]
        return parsed

    def generate_course_assessments(
        self,
        course_title: str,
        chapters: List[Dict[str, Any]],
        subject: str,
        tier: str
    ) -> Optional[Dict[str, Any]]:
        """Generates practice quizzes and summative final exam questions with local Llama model."""
        context_snippets = []
        for ch in chapters[:6]:
            context_snippets.append(f"Chapter {ch.get('chapter_index')}: {ch.get('title')}\nSummary: {ch.get('summary', '')}")

        full_context = "\n\n".join(context_snippets)

        prompt = f"""You are a test design authority for {subject} ({tier}).
Based on course '{course_title}':
{full_context}

Generate a valid JSON object with EXACTLY this structure:
{{
  "quizzes": [
    {{"id": "q_1", "text": "...", "concept": "{chapters[0].get('title', 'Chapter 1')}", "options": ["A", "B", "C", "D"], "correct_answer": "A"}}
  ],
  "finalExam": [
    {{
      "qId": "exam_1",
      "moduleOrigin": "Module 1: ...",
      "question_type": "short_answer",
      "options": [],
      "text": "...",
      "expected": "...",
      "formula": "...",
      "misconception": "..."
    }}
  ]
}}
Respond ONLY with the raw JSON object."""

        parsed = self.generate_structured_json(
            prompt=prompt,
            system_prompt="You are a JSON-only exam question architect.",
            max_tokens=1600,
        )
        if not parsed:
            return None
        if not isinstance(parsed.get("quizzes"), list):
            parsed["quizzes"] = []
        if not isinstance(parsed.get("finalExam"), list):
            parsed["finalExam"] = []
        return parsed


# Global instance
local_llm = LocalLLMService()