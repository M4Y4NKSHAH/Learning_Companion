import os
import json
import time
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, List


class LocalLLMService:
    """
    100% Offline Local LLM Inference Engine for Llama-3.2-3B-Instruct / Qwen.
    Connects to local Ollama instance (http://localhost:11434) or llama-cpp server
    with zero cloud token dependency and zero API costs.
    """
    def __init__(self, base_url: str = "http://localhost:11434", model_name: str = "llama3.2:3b"):
        self.base_url = os.getenv("LOCAL_LLM_URL", base_url)
        self.model_name = os.getenv("LOCAL_LLM_MODEL", model_name)
        self._available_cache: Optional[bool] = None
        self._available_ts: float = 0
        self._CACHE_TTL = 25.0  # seconds

    def is_available(self) -> bool:
        """Checks if local Ollama or llama-cpp server is actively running (cached for 25s)."""
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

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 1024,
        timeout: int = 75
    ) -> Optional[str]:
        """Generates text from local Llama-3.2-3B-Instruct instance with timeout and context protection."""
        if not self.is_available():
            return None

        payload = {
            "model": self.model_name,
            "prompt": prompt[:3500],  # Protect against KV cache OOM
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens
            }
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            req = urllib.request.Request(
                f"{self.base_url}/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=timeout) as res:
                if res.status == 200:
                    data = json.loads(res.read().decode("utf-8"))
                    return data.get("response", "").strip()
        except Exception as e:
            print(f"[LocalLLMService] Inference warning: {e}")
            return None

        return None

    @staticmethod
    def _clean_json_str(text: str) -> str:
        """Strips markdown fences and isolates valid JSON object/array substrings."""
        cleaned = text.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```", 1)[1].split("```", 1)[0].strip()
        
        # If still wrapped in surrounding text, extract between first { and last } or [ and ]
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

    def summarize_chapter_and_generate_cards(self, chapter_title: str, chapter_content: str, subject: str) -> Optional[Dict[str, Any]]:
        """Generates structured summary and 3 flashcards using local Llama model."""
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

        response_text = self.generate(prompt=prompt, system_prompt="You are a JSON-only curriculum generator.")
        if not response_text:
            return None

        try:
            clean_json = self._clean_json_str(response_text)
            return json.loads(clean_json)
        except Exception as e:
            print(f"[LocalLLMService] JSON parsing failed: {e}")
            return None

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

        response_text = self.generate(prompt=prompt, system_prompt="You are a JSON-only exam question architect.")
        if not response_text:
            return None

        try:
            clean_json = response_text.strip()
            if clean_json.startswith("```json"):
                clean_json = clean_json[7:]
            if clean_json.startswith("```"):
                clean_json = clean_json[3:]
            if clean_json.endswith("```"):
                clean_json = clean_json[:-3]
            return json.loads(clean_json.strip())
        except Exception as e:
            print(f"[LocalLLMService] Assessment JSON parsing failed: {e}")
            return None


# Global instance
local_llm = LocalLLMService()
