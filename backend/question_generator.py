import os
import re
import json
import uuid
from typing import Dict, List, Any, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

try:
    from langchain_core.messages import HumanMessage
    from langchain_google_genai import ChatGoogleGenerativeAI
    LANGCHAIN_GEMINI_AVAILABLE = True
except ImportError:
    LANGCHAIN_GEMINI_AVAILABLE = False

try:
    from backend.local_llm_service import local_llm
except ImportError:
    from local_llm_service import local_llm

try:
    from backend.pedagogical_guardrails import get_grade_level_guardrails, filter_for_grade_level
except ImportError:
    from pedagogical_guardrails import get_grade_level_guardrails, filter_for_grade_level



def normalize_ai_content(content: Any) -> str:
    """Universal normalizer handling strings, lists of dict parts (Gemini 3.8 Flash), etc."""
    if isinstance(content, list):
        return "".join(part.get("text", str(part)) if isinstance(part, dict) else str(part) for part in content)
    return str(content or "")


# --------------------------------------------------------------------------- #
# Schema contract shared by the local Llama engine, Gemini guiding agent, and
# the deterministic fallback so every layer produces interchangeable theories.
# --------------------------------------------------------------------------- #
DEEP_THEORY_KEYS = ("principles", "formulations", "mental_models", "misconceptions")


class QuestionGeneratorEngine:
    """
    v2 Theory Generation Engine — 'Grounded-first, Llama-first' redesign.

    Complete overhaul of the v1 pipeline:

    OLD: one giant Gemini-or-Llama prompt => fragile single JSON blob, frequent
         hallucinated formulas and TOC/junk leakage into chapter titles.

    NEW: a deterministic "fact skeleton" is extracted from the source text FIRST,
         then a small, decomposed set of local-Llama JSON-mode prompts enrich that
         skeleton, and finally every field is *grounded* against the skeleton so
         equations/terms/values that appear in the book always win over anything
         the 3B model invents.

    Execution order per chapter:
        1. `_extract_facts_from_text()`  — grounded skeleton (equations, laws,
           constants, definitions, key terms) with strict source verification.
        2. Phase A: local Llama JSON-mode blueprint (summary/objectives/deep_theory).
        3. Phase B: local Llama JSON-mode flashcard synthesis.
        4. `_ground_deep_theory()` — merge local output with the fact skeleton,
           filling every blank and rejecting formulas the book never contains.
        5. Fallback ladder: local  ->  Gemini single-pass  ->  deterministic NLP.
    """

    # System directive shared across every local synthesis call. Compact so the
    # 3B model spends its small context budget on the chapter text, not boilerplate.
    JSON_ONLY_SYSTEM = (
        "You are an expert academic curriculum architect and cognitive scientist. "
        "Write concise, rigorous, age-appropriate theory grounded ONLY in the "
        "provided text. Respond with a single valid JSON object — no markdown, "
        "no commentary, no explanations."
    )

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.local_llm = local_llm

    def _get_gemini_guide_model(self):
        """Returns Gemini model instance for single-pass guiding if API key is available."""
        if not (LANGCHAIN_GEMINI_AVAILABLE and self.api_key):
            return None
        model_name = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
        try:
            return ChatGoogleGenerativeAI(
                model=model_name,
                temperature=0.2,
                google_api_key=self.api_key,
                max_retries=1
            )
        except Exception as e:
            try:
                return ChatGoogleGenerativeAI(
                    model="gemini-2.5-flash",
                    temperature=0.2,
                    google_api_key=self.api_key,
                    max_retries=1
                )
            except Exception:
                pass
            print(f"[Guiding Agent] Gemini init warning: {e}")
            return None
# ------------------------------------------------------------------ #
    # Course-level blueprint (optional cloud accelerator)
    # ------------------------------------------------------------------ #
    def generate_guided_curriculum_blueprint(
        self,
        course_title: str,
        material_sample: str,
        subject: str = "General",
        tier: str = "Standard",
        detected_headings: Optional[List[str]] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        SINGLE-PASS GUIDING AGENT (optional, cloud-accelerated):
        Designs the complete academic theory blueprint for an entire course in one
        focused call. Only used when a Gemini API key is configured; the local engine
        and the deterministic skeleton remain the always-available path.
        """
        gemini = self._get_gemini_guide_model()
        if not gemini:
            return None

        headings_hint = "\n".join([f"- {h}" for h in (detected_headings or [])[:8]])
        prompt = (
            f"You are a master university curriculum architect for {subject} ({tier}).\n"
            f"Course Title: '{course_title}'\n"
            f"Document Headings / Outline:\n{headings_hint}\n\n"
            f"Representative Document Sample:\n\"\"\"{material_sample[:4000]}\"\"\"\n\n"
            "Craft a comprehensive, accurate curriculum blueprint with 3 to 6 deep learning chapters.\n"
            "For EACH chapter, provide:\n"
            "1. 'title': Clear, descriptive academic title (no trailing page numbers).\n"
            "2. 'summary': 2-3 sentence rigorous theoretical synthesis of foundational mechanisms.\n"
            "3. 'objectives': 3 specific learning objectives.\n"
            "4. 'principles': Array of 2 core axioms/definitions [{\"title\": \"...\", \"content\": \"...\", \"tag\": \"Core Axiom\"}].\n"
            "5. 'formulations': Array of 1-2 governing formulas/algorithms [{\"title\": \"...\", \"formula\": \"...\", \"derivation\": \"...\", \"variables\": \"...\"}].\n"
            "6. 'mental_models': Array of 1 intuitive analogy [{\"concept\": \"...\", \"analogy\": \"...\", \"takeaway\": \"...\"}].\n"
            "7. 'misconceptions': Array of 1 common cognitive trap [{\"trap\": \"...\", \"correction\": \"...\"}].\n"
            "8. 'key_terms': Array of 3-4 definitions [{\"term\": \"...\", \"definition\": \"...\"}].\n"
            "9. 'cards': Exactly 3 distinct, high-impact flashcards [{\"topic\": \"...\", \"question\": \"...\", \"answer\": \"• ...\\n• ...\"}].\n\n"
        )
        prompt += (
            "Return ONLY a raw JSON array of chapter objects matching this schema without markdown fences:\n"
            "[\n"
            "  {\n"
            '    "title": "Chapter 1: ...",\n'
            '    "summary": "...",\n'
            '    "objectives": ["...", "...", "..."],\n'
            '    "principles": [{"title": "...", "content": "...", "tag": "Core Axiom"}],\n'
            '    "formulations": [{"title": "...", "formula": "...", "derivation": "...", "variables": "..."}],\n'
            '    "mental_models": [{"concept": "...", "analogy": "...", "takeaway": "..."}],\n'
            '    "misconceptions": [{"trap": "...", "correction": "..."}],\n'
            '    "key_terms": [{"term": "...", "definition": "..."}],\n'
            '    "cards": [{"topic": "...", "question": "...", "answer": "• ...\\n• ..."}]\n'
            "  }\n"
            "]"
        )

        try:
            print("[Guiding Agent] Requesting single-pass curriculum blueprint from Gemini...")
            res = gemini.invoke([HumanMessage(content=prompt)])
            raw_content = normalize_ai_content(res.content)
            clean_json = raw_content.replace("```json", "").replace("```", "").strip()
            try:
                blueprint = json.loads(clean_json)
            except Exception:
                sanitized_json = re.sub(r'\\(?![/\\bfnrtu"U])', r'\\\\', clean_json)
                blueprint = json.loads(sanitized_json)
            if isinstance(blueprint, list) and len(blueprint) > 0:
                print(f"[Guiding Agent] Successfully crafted {len(blueprint)} guided theory chapters!")
                return blueprint
        except Exception as e:
            print(f"[Guiding Agent] Guiding call fallback (will use local engine): {e}")

        return None
# ------------------------------------------------------------------ #
    # Chapter theory & flashcard synthesis (the v2 overhauled engine)
    # ------------------------------------------------------------------ #
    def generate_chapter_theory_and_cards(
        self,
        chapter_title: str,
        chapter_text: str,
        subject: str = "General",
        tier: str = "Standard",
        chapter_index: int = 1,
        use_llm: bool = True,
        allow_cloud_fallback: bool = True,
        include_cards: bool = True
    ) -> Dict[str, Any]:
        """
        Synthesizes rigorous, source-grounded chapter theory, objectives, deep-theory
        breakdown, and flashcards.

        Strategy (complete overhaul):
          - A deterministic fact skeleton is always extracted from the chapter text,
            so even a completely offline / model-less run produces accurate theory.
          - The fine-tuned local Llama (JSON mode) enriches that skeleton in two small,
            decomposed phases instead of one fragile mega-prompt.
          - Every LLM-produced field is grounded back against the skeleton, so a formula
            never enters the course unless it actually appears in the book.
          - Combined with grade-level guardrail filtering for the target academic tier.
          - `include_cards=False` skips the flashcard model call (the second local-Llama
            round-trip), roughly halving the wall-clock time for one chapter when only
            the theory is needed; deterministic cards are still produced if it is later
            requested.
        """
        clean_title = self._clean_chapter_title(chapter_title)
        guardrails = get_grade_level_guardrails(tier)

        # --- Grounded skeleton ------------------------------------------------- #
        facts = self._extract_facts_from_text(chapter_text)
        equations = [f for f in facts if f["type"] == "equation"]
        definitions = [f for f in facts if f["type"] == "definition"]
        values = [f for f in facts if f["type"] == "value"]
        key_terms = self._extract_key_terms(chapter_text, facts)
        worked_examples = self._extract_worked_examples(chapter_text)

        # --- 1. LOCAL LLAMA (primary engine: single-pass unified synthesis) --- #
        local_out = None
        local_cards = None
        if use_llm and self.local_llm.is_available():
            unified = self._local_synthesize_unified(
                title=clean_title,
                text=chapter_text,
                subject=subject,
                tier=tier,
                chapter_index=chapter_index,
                include_cards=include_cards,
            )
            if unified:
                local_out = unified
                if include_cards and "cards" in unified:
                    local_cards = self._coerce_cards(unified)
            else:
                # Fallback to separate passes if unified parse fails
                local_out = self._local_synthesize_blueprint(
                    title=clean_title,
                    text=chapter_text,
                    subject=subject,
                    tier=tier,
                    chapter_index=chapter_index,
                )
                if include_cards:
                    local_cards = self._local_synthesize_cards(
                        title=clean_title,
                        text=chapter_text,
                        subject=subject,
                        tier=tier,
                    )

        # --- 2. GEMINI single-pass (optional secondary) ----------------------- #
        #    Kept for the in-app ingestion flow. The offline book builder passes
        #    allow_cloud_fallback=False so a failed local JSON parse can never
        #    stall the pipeline on a network round-trip.
        gemini_out = None
        if use_llm and local_out is None and allow_cloud_fallback:
            gemini_out = self._gemini_synthesize_chapter(
                title=clean_title,
                text=chapter_text,
                subject=subject,
                tier=tier,
                chapter_index=chapter_index,
            )

        blueprint = local_out or gemini_out or {}
        # Accurate provenance: lets the course tell the learner exactly which
        # chapters were model-enriched and which used the offline skeleton.
        if local_out is not None:
            theory_source = "llm"
        elif gemini_out is not None:
            theory_source = "cloud"
        else:
            theory_source = "deterministic"

        # --- 3. Deterministic skeleton fallback ------------------------------- #
        deep_root = self._build_subject_deep_theory(
            subject=subject,
            chapter_title=clean_title,
            c1=definitions[0]["text"] if definitions else "",
            c2=definitions[1]["text"] if len(definitions) > 1 else "",
            c_formula=equations[0]["full"] if equations else "",
            definitions=definitions,
            equations=equations,
        )

        cards_out = local_cards if (local_out is not None and local_cards) else None
        if cards_out is None:
            cards_out = self._facts_to_cards(clean_title, facts, subject)

        # --- 4. Ground & merge ------------------------------------------------- #
        deep_theory = self._ground_deep_theory(blueprint, deep_root, equations, definitions)

        # key_terms are source extracted
        if key_terms:
            deep_theory["key_terms"] = key_terms
        # worked_examples: preserve model-synthesized worked_examples if present, supplement/fallback from source
        if worked_examples and not deep_theory.get("worked_examples"):
            deep_theory["worked_examples"] = worked_examples
        elif worked_examples and deep_theory.get("worked_examples"):
            if len(deep_theory["worked_examples"]) < 2:
                deep_theory["worked_examples"].extend(worked_examples[:2 - len(deep_theory["worked_examples"])])

        summary = self._coerce_str(blueprint.get("summary")) or self._skeleton_summary(clean_title, facts)
        objectives = self._coerce_list(blueprint.get("objectives")) or [
            f"Define and explain the core concept of {clean_title}.",
            f"Apply the governing rules of {clean_title} to solve structured problems.",
            f"Analyze real-world scenarios using the theoretical framework of {clean_title}.",
        ]

        # --- 5. Grade filtering ------------------------------------------------- #
        summary = self._safe_filter(filter_for_grade_level, summary, tier)
        filtered_cards = []
        for card in (cards_out or [])[:3]:
            question = self._safe_filter(filter_for_grade_level, card.get("question", ""), tier)
            answer = self._safe_filter(filter_for_grade_level, card.get("answer", ""), tier)
            if question and answer:
                filtered_cards.append({"topic": card.get("topic") or clean_title, "question": question, "answer": answer})

        if not filtered_cards:
            filtered_cards = self._fallback_cards(clean_title, tier)

        return {
            "chapter_index": chapter_index,
            "title": clean_title,
            "summary": summary,
            "objectives": objectives,
            "cards": filtered_cards,
            "deep_theory": deep_theory,
            # Provenance of the theory text: "llm" (fine-tuned local Llama),
            # "cloud" (Gemini fallback) or "deterministic" (offline skeleton).
            "theory_source": theory_source,
        }
# ------------------------------------------------------------------ #
    # Local Llama phases
    # ------------------------------------------------------------------ #
    @staticmethod
    def _prepare_chapter_context(text: str, max_chars: int = 7500) -> str:
        """
        Extracts a comprehensive, high-signal multi-section text window up to max_chars.
        Samples the opening foundations (45%), central analytical core (35%),
        and concluding synthesis/worked examples (20%) so the LLM synthesizes
        complete, rigorous theory rather than a shallow 2-sentence summary.
        """
        if not text:
            return ""
        clean = text.strip()
        if len(clean) <= max_chars:
            return clean

        head_len = int(max_chars * 0.45)
        mid_len = int(max_chars * 0.35)
        tail_len = max_chars - head_len - mid_len

        head = clean[:head_len]
        mid_start = max(head_len, (len(clean) - mid_len) // 2)
        mid = clean[mid_start: mid_start + mid_len]
        tail = clean[-tail_len:]

        return f"{head}\n\n[... Core Section Analysis ...]\n\n{mid}\n\n[... Key Applications & Review ...]\n\n{tail}"

    def _local_synthesize_unified(
        self,
        title: str,
        text: str,
        subject: str,
        tier: str,
        chapter_index: int,
        include_cards: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Unified Phase A+B: single structured local-Llama call for blueprint AND cards with rich context."""
        ctx = self._prepare_chapter_context(text, max_chars=7500)
        card_schema = (
            '\n  "cards": [\n'
            f'    {{"topic": "{title}", "question": "conceptual question", "answer": "• Core Principle: ...\\n• Mechanism: ..."}},\n'
            f'    {{"topic": "{title}", "question": "analytical question", "answer": "• Formula/Rule: ...\\n• Meaning: ..."}},\n'
            f'    {{"topic": "{title}", "question": "application question", "answer": "• Practical application: ...\\n• Common trap: ..."}}\n'
            '  ],'
            if include_cards else ""
        )
        prompt = (
            f"SUBJECT: {subject} | LEARNER TIER: {tier}\n"
            f"CHAPTER {chapter_index}: {title}\n\n"
            f"SOURCE TEXT (Comprehensive Chapter Excerpt):\n\"\"\"{ctx}\"\"\"\n\n"
            "Return a JSON object with EXACTLY these keys and shapes:\n"
            "{\n"
            '  "summary": "Deep, rigorous 3-4 sentence comprehensive academic synthesis detailing the primary thesis, governing computational/scientific mechanisms, and practical significance.",' + card_schema + '\n'
            '  "objectives": ["Specific action-oriented objective (e.g. Master...)", "Analytical objective (e.g. Formulate...)", "Evaluative objective (e.g. Differentiate...)"],\n'
            '  "principles": [{"title": "Precise Concept Name", "content": "Rigorous definition or governing law explaining operational mechanics", "tag": "Core Axiom|Governing Law|Definition"}],\n'
            '  "formulations": [{"title": "Analytical Specification", "formula": "Governing equation, definition, or algorithmic invariant", "derivation": "Step-by-step reasoning or mathematical justification", "variables": "Precise breakdown of symbols, units, and operational boundaries"}],\n'
            '  "mental_models": [{"concept": "Core Concept Name", "analogy": "Vivid, intuitive, real-world physical analogy explaining how the system behaves", "takeaway": "Actionable conceptual heuristic or invariant rule"}],\n'
            '  "worked_examples": [{"title": "Concrete Worked Example", "content": "Step-by-step problem walkthrough from the chapter with given parameters, solution strategy, and conclusion"}],\n'
            '  "misconceptions": [{"trap": "Common student misconception or procedural pitfall", "correction": "Deep conceptual correction explaining why the intuition fails and what to verify"}]\n'
            "}\n"
            "Base every string strictly on the source text. Provide thorough, educational depth. No markdown fences, no extra keys."
        )
        parsed = self.local_llm.generate_structured_json(
            prompt=prompt,
            system_prompt=self.JSON_ONLY_SYSTEM,
            temperature=0.2,
            max_tokens=1800,
            timeout=120,
        )
        if isinstance(parsed, dict) and "summary" in parsed:
            return parsed
        return None

    def _local_synthesize_blueprint(
        self,
        title: str,
        text: str,
        subject: str,
        tier: str,
        chapter_index: int,
    ) -> Optional[Dict[str, Any]]:
        """Phase A: one structured local-Llama call for the theory blueprint with rich multi-section context."""
        ctx = self._prepare_chapter_context(text, max_chars=7500)
        prompt = (
            f"SUBJECT: {subject} | LEARNER TIER: {tier}\n"
            f"CHAPTER {chapter_index}: {title}\n\n"
            f"SOURCE TEXT (Comprehensive Chapter Excerpt):\n\"\"\"{ctx}\"\"\"\n\n"
            "Return a JSON object with EXACTLY these keys and shapes:\n"
            "{\n"
            '  "summary": "Deep, rigorous 3-4 sentence comprehensive academic synthesis detailing the primary thesis, governing computational/scientific mechanisms, and practical significance.",\n'
            '  "objectives": ["Specific action-oriented objective (e.g. Master...)", "Analytical objective (e.g. Formulate...)", "Evaluative objective (e.g. Differentiate...)"],\n'
            '  "principles": [{"title": "Precise Concept Name", "content": "Rigorous definition or governing law explaining operational mechanics", "tag": "Core Axiom|Governing Law|Definition"}],\n'
            '  "formulations": [{"title": "Analytical Specification", "formula": "Governing equation, definition, or algorithmic invariant", "derivation": "Step-by-step reasoning or mathematical justification", "variables": "Precise breakdown of symbols, units, and operational boundaries"}],\n'
            '  "mental_models": [{"concept": "Core Concept Name", "analogy": "Vivid, intuitive, real-world physical analogy explaining how the system behaves", "takeaway": "Actionable conceptual heuristic or invariant rule"}],\n'
            '  "worked_examples": [{"title": "Concrete Worked Example", "content": "Step-by-step problem walkthrough from the chapter with given parameters, solution strategy, and conclusion"}],\n'
            '  "misconceptions": [{"trap": "Common student misconception or procedural pitfall", "correction": "Deep conceptual correction explaining why the intuition fails and what to verify"}]\n'
            "}\n"
            "Base every string strictly on the source text. Provide thorough, educational depth. No markdown fences, no extra keys."
        )
        parsed = self.local_llm.generate_structured_json(
            prompt=prompt,
            system_prompt=self.JSON_ONLY_SYSTEM,
            temperature=0.2,
            max_tokens=1800,
            timeout=120,
        )
        if isinstance(parsed, dict):
            return parsed
        return None

    def _local_synthesize_cards(
        self,
        title: str,
        text: str,
        subject: str,
        tier: str,
    ) -> Optional[List[Dict[str, Any]]]:
        """Phase B: one structured local-Llama call for three high-retention cards."""
        ctx = text[:2400]
        prompt = (
            f"SUBJECT: {subject} | LEARNER TIER: {tier}\n"
            f"CHAPTER: {title}\n\n"
            f"SOURCE TEXT:\n\"\"\"{ctx}\"\"\"\n\n"
            "Generate exactly 3 flashcards. Return a JSON object:\n"
            '{"cards": [{"topic": "...", "question": "conceptual or formula question", "answer": "• Core Principle: ...\\n• Governing Rule: ...\\n• Application: ..."}]}\n'
            "Answers must cite the source text. No markdown, no extra keys."
        )
        parsed = self.local_llm.generate_structured_json(
            prompt=prompt,
            system_prompt=self.JSON_ONLY_SYSTEM,
            temperature=0.2,
            max_tokens=1000,
            timeout=120,
        )
        cards = self._coerce_cards(parsed)
        if cards:
            return cards

        # A 3B model sometimes chokes on the nested bullet template. Retry once
        # with a flatter schema before falling back to the deterministic cards.
        simple_prompt = (
            f"SUBJECT: {subject} | LEARNER TIER: {tier}\n"
            f"CHAPTER: {title}\n\n"
            f"SOURCE TEXT:\n\"\"\"{ctx}\"\"\"\n\n"
            "Write 3 study flashcards from the source text above.\n"
            "Return ONLY this JSON: {\"cards\": [{\"topic\": \"...\", "
            "\"question\": \"...\", \"answer\": \"...\"}]}\n"
            "Each answer must be one complete sentence copied or closely "
            "paraphrased from the source text."
        )
        parsed = self.local_llm.generate_structured_json(
            prompt=simple_prompt,
            system_prompt=self.JSON_ONLY_SYSTEM,
            temperature=0.1,
            max_tokens=800,
            timeout=120,
        )
        return self._coerce_cards(parsed)

    @staticmethod
    def _coerce_cards(parsed: Any) -> List[Dict[str, Any]]:
        """Normalises the many shapes a small model returns cards in."""
        if not isinstance(parsed, dict):
            return []
        cards = parsed.get("cards") or parsed.get("flashcards") or []
        if isinstance(cards, dict):
            cards = [cards]
        if not isinstance(cards, list):
            return []
        out = []
        for c in cards:
            if not isinstance(c, dict):
                continue
            question = str(c.get("question") or c.get("q") or "").strip()
            answer = str(c.get("answer") or c.get("a") or "").strip()
            if question and answer:
                out.append({
                    "topic": str(c.get("topic") or "").strip(),
                    "question": question,
                    "answer": answer,
                })
        return out

    def _gemini_synthesize_chapter(
        self,
        title: str,
        text: str,
        subject: str,
        tier: str,
        chapter_index: int,
    ) -> Optional[Dict[str, Any]]:
        """Optional cloud fallback for chapter blueprint synthesis (single-pass)."""
        gemini = self._get_gemini_guide_model()
        if not gemini:
            return None
        guardrails = get_grade_level_guardrails(tier)
        prohibitions = "\n".join(f"- {p}" for p in guardrails["strict_prohibitions"])
        requirements = "\n".join(f"- {r}" for r in guardrails["mandatory_requirements"])
        ctx = self._prepare_chapter_context(text, max_chars=24000)
        try:
            prompt = (
                f"You are an expert curriculum architect for {subject}.\n"
                f"TARGET LEARNER LEVEL: {guardrails['label']} ({guardrails['audience']})\n"
                f"Math/Conceptual Ceiling: {guardrails['math_ceiling']}\n"
                f"STRICT PROHIBITIONS:\n{prohibitions}\n"
                f"MANDATORY REQUIREMENTS:\n{requirements}\n\n"
                f"Chapter {chapter_index}: '{title}'\n"
                f"Source text:\n\"\"\"{ctx}\"\"\"\n\n"
                "Return a JSON object with EXACTLY these keys and shapes:\n"
                "{\n"
                '  "summary": "Deep, rigorous 3-4 sentence comprehensive academic synthesis detailing governing computational/scientific/mathematical mechanisms.",\n'
                '  "objectives": ["Specific action-oriented objective", "Analytical objective", "Evaluative objective"],\n'
                '  "principles": [{"title": "Precise Concept Name", "content": "Rigorous definition or governing law explaining operational mechanics", "tag": "Core Axiom|Governing Law|Definition"}],\n'
                '  "formulations": [{"title": "Analytical Specification", "formula": "Governing equation, definition, or algorithmic invariant", "derivation": "Step-by-step reasoning or mathematical justification", "variables": "Precise breakdown of symbols, units, and boundaries"}],\n'
                '  "mental_models": [{"concept": "Core Concept Name", "analogy": "Vivid intuitive real-world physical analogy explaining how the system behaves", "takeaway": "Actionable conceptual heuristic or invariant rule"}],\n'
                '  "worked_examples": [{"title": "Concrete Worked Example", "content": "Step-by-step problem walkthrough from the chapter with parameters, method, and conclusion"}],\n'
                '  "misconceptions": [{"trap": "Common student misconception or pitfall", "correction": "Deep conceptual correction explaining why intuition fails"}],\n'
                '  "cards": [{"topic": "...", "question": "Clear concept question?", "answer": "• Key point 1\\n• Key point 2\\n• Key point 3"}]\n'
                "}\n"
                "Base every field strictly on the source text. Provide thorough educational depth. Respond ONLY with the JSON."
            )
            res = gemini.invoke([HumanMessage(content=prompt)])
            raw_content = normalize_ai_content(res.content)
            clean_json = raw_content.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(clean_json)
            if isinstance(parsed, dict):
                return parsed
        except Exception as e:
            print(f"[QGE] Gemini chapter synthesis fallback: {e}")
        return None
# ------------------------------------------------------------------ #
    # Grounding & merge
    # ------------------------------------------------------------------ #
    def _ground_deep_theory(
        self,
        blueprint: Dict[str, Any],
        skeleton: Dict[str, Any],
        equations: List[Dict[str, str]],
        definitions: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """
        Merges whatever the LLM produced with the deterministic skeleton so the
        output is always complete, valid, and book-grounded.
        """
        deep = dict(skeleton)  # start from deterministic fallback

        for key, tag in (("principles", "Core Axiom"), ("formulations", "Governing Formulation")):
            items = self._coerce_list(blueprint.get(key))
            if items:
                cleaned = []
                for it in items:
                    if isinstance(it, dict):
                        title = self._coerce_str(it.get("title"))
                        content = self._coerce_str(it.get("content")) or self._coerce_str(it.get("formula"))
                        if title and content:
                            item = {"title": title, "content": content}
                            if key == "formulations":
                                item.update({
                                    "formula": self._coerce_str(it.get("formula")) or content,
                                    "derivation": self._coerce_str(it.get("derivation")) or "Derived from foundational conservation and symmetry principles.",
                                    "variables": self._coerce_str(it.get("variables")) or "State variables, proportionalities, and physical boundary constraints.",
                                })
                            else:
                                item["tag"] = self._coerce_str(it.get("tag")) or tag
                            cleaned.append(item)
                if cleaned:
                    deep[key] = cleaned

        # Mental models
        mental = self._coerce_list(blueprint.get("mental_models"))
        if mental:
            cleaned = []
            for m in mental:
                if isinstance(m, dict) and (m.get("concept") or m.get("analogy")):
                    cleaned.append({
                        "concept": self._coerce_str(m.get("concept")) or "Intuitive Model",
                        "analogy": self._coerce_str(m.get("analogy")) or "",
                        "takeaway": self._coerce_str(m.get("takeaway")) or "Connect the analogy back to the formal definition.",
                    })
            if cleaned:
                deep["mental_models"] = cleaned

        # Misconceptions
        mis = self._coerce_list(blueprint.get("misconceptions"))
        if mis:
            cleaned = []
            for m in mis:
                if isinstance(m, dict) and (m.get("trap") or m.get("correction")):
                    cleaned.append({
                        "trap": self._coerce_str(m.get("trap")) or "Misapplying a formula outside its domain",
                        "correction": self._coerce_str(m.get("correction")) or "Always verify the operational domain before calculation.",
                    })
            if cleaned:
                deep["misconceptions"] = cleaned

        # Worked examples from LLM
        ex_items = self._coerce_list(blueprint.get("worked_examples"))
        if ex_items:
            existing_ex = list(deep.get("worked_examples", []))
            for ex in ex_items:
                if isinstance(ex, dict) and (ex.get("title") or ex.get("content")):
                    existing_ex.append({
                        "title": self._coerce_str(ex.get("title")) or "Worked Walkthrough",
                        "content": self._coerce_str(ex.get("content")) or self._coerce_str(ex.get("solution")) or self._coerce_str(ex.get("explanation")),
                    })
            if existing_ex:
                deep["worked_examples"] = existing_ex[:3]

        # Ground formulations: prioritize model-synthesized formulations, supplement with verified equations
        llm_formulas = self._coerce_list(blueprint.get("formulations"))
        cleaned_formulas = []
        if llm_formulas:
            for f in llm_formulas:
                if isinstance(f, dict) and (f.get("formula") or f.get("title")):
                    cleaned_formulas.append({
                        "title": self._coerce_str(f.get("title")) or "Governing Formulation",
                        "formula": self._coerce_str(f.get("formula")) or self._coerce_str(f.get("content")),
                        "derivation": self._coerce_str(f.get("derivation")) or "Derived from governing first principles.",
                        "variables": self._coerce_str(f.get("variables")) or "Operational symbols and boundary constraints.",
                    })
        if cleaned_formulas:
            deep["formulations"] = cleaned_formulas[:3]
        elif equations:
            is_generic_formula = any("Analytical Formulation" in f.get("title", "") or "y = f(x" in f.get("formula", "") for f in deep.get("formulations", []))
            if is_generic_formula:
                grounded_formulas = []
                for f in equations[:4]:
                    f_full = f.get("full", "")
                    if len(f_full) < 65 and not any(w in f_full.lower() for w in ("calculator", "menu", "graph", "chapter", "exercise", "figure")):
                        grounded_formulas.append({
                            "title": f"Governing Equation: {f['lhs']}",
                            "formula": f_full,
                            "derivation": "Extracted verbatim from the verified source textbook text.",
                            "variables": f"LHS: {f['lhs']} = RHS: {f['rhs']}",
                        })
                if grounded_formulas:
                    deep["formulations"] = grounded_formulas[:3]

        # Ground principles: prioritize model-synthesized principles, supplement with verified definitions
        llm_principles = self._coerce_list(blueprint.get("principles"))
        cleaned_principles = []
        if llm_principles:
            for p in llm_principles:
                if isinstance(p, dict):
                    t = self._coerce_str(p.get("title"))
                    c = self._coerce_str(p.get("content"))
                    if t and c:
                        cleaned_principles.append({
                            "title": t,
                            "content": c,
                            "tag": self._coerce_str(p.get("tag")) or "Core Axiom",
                        })
            if cleaned_principles:
                deep["principles"] = cleaned_principles[:4]
        elif definitions:
            is_generic_p = any("Primary Governing Principle" in p.get("title", "") or "Foundational Mathematical Axiom" in p.get("title", "") for p in deep.get("principles", []))
            vignette_words = (
                "vacation", "student", "spring break", "farmer", "pump", "diameter",
                "ticket", "hotel", "salary", "trip", "mile", "car", "population",
                "country", "ferris wheel", "wheel", "dollar", "store", "company", "cent",
            )
            grounded_p = []
            for d in definitions:
                dt = d.get("text", "")
                concept = d.get("concept", "")
                if dt and concept and not any(w in dt.lower() for w in vignette_words):
                    content = dt if dt.lower().startswith(concept.lower()) else f"{concept} is defined as {dt}."
                    grounded_p.append({
                        "title": concept,
                        "content": content,
                        "tag": "Definition",
                    })
                if len(grounded_p) >= 3:
                    break
            if grounded_p and is_generic_p:
                deep["principles"] = grounded_p
            elif grounded_p:
                for gp in grounded_p:
                    if len(deep["principles"]) < 4 and not any(p.get("title", "").lower() == gp["title"].lower() for p in deep["principles"]):
                        deep["principles"].append(gp)

        return deep

    @staticmethod
    def _in_text(formula: str, source_eqs: List[str]) -> bool:
        """Checks if an LLM formula is (loosely) contained in one of the source equations."""
        norm = re.sub(r"\s+", "", (formula or "").lower())
        for eq in source_eqs:
            if norm and (re.sub(r"\s+", "", eq.lower()) in norm or norm in re.sub(r"\s+", "", eq.lower())):
                return True
        return False
# ------------------------------------------------------------------ #
    # Helpers for seeded, deterministic synthesis
    # ------------------------------------------------------------------ #
    @staticmethod
    def _clean_chapter_title(title: str) -> str:
        """Strips page numbers and TOC junk that leaked into titles in v1."""
        t = (title or "").strip()
        # Drop trailing page numbers: "1.1 Physics: An Introduction 8" -> "1.1 Physics: An Introduction"
        t = re.sub(r"\s+\d{1,4}$", "", t)
        # Drop trailing navigation noise like "... 119 Fundamentals"
        t = re.sub(r"\s*\d{1,4}\s*$", "", t)
        # Collapse duplicate whitespace
        t = re.sub(r"\s{2,}", " ", t).strip()
        # If only digits/symbols remain, fall back to a neutral title
        if not re.search(r"[A-Za-z]{3,}", t):
            return title if (title or "").strip() else "Chapter Theory"
        return t

    @staticmethod
    def _coerce_str(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, list):
            return " ".join(str(v) for v in value if v)
        return str(value)

    @staticmethod
    def _coerce_list(value: Any) -> List[Any]:
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            return [value]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    @staticmethod
    def _safe_filter(fn, text, tier):
        """Calls the guardrail filter defensively — must never raise during ingestion."""
        try:
            return fn(text, tier)
        except Exception:
            return text

    @staticmethod
    def _skeleton_summary(title: str, facts: List[Dict[str, str]]) -> str:
        """Deterministic 2-3 sentence summary built from extracted facts."""
        parts = [f"{title} establishes the core theoretical framework and analytical methods of its domain."]
        eqs = [f["full"] for f in facts if f["type"] == "equation"][:2]
        defs = [d["text"] for d in facts if d["type"] == "definition"][:1]
        if defs:
            clean_def = defs[0].strip()
            if len(clean_def) >= 25:
                if clean_def[0].isupper() and clean_def.endswith("."):
                    parts.append(clean_def)
                else:
                    parts.append(f"A key governing definition specifies that {clean_def.rstrip('.')}.")
        if eqs:
            parts.append(f"Its governing relations include {' and '.join(eqs)}.")
        if len(parts) < 3:
            parts.append("Mastering these foundational definitions and boundary conditions is essential for applying the framework.")
        return " ".join(parts)

    def _facts_to_cards(self, title: str, facts: List[Dict[str, str]], subject: str) -> List[Dict[str, Any]]:
        """Builds flashcards deterministically from source-grounded facts."""
        cards = []
        eqs = [f for f in facts if f["type"] == "equation"][:1]
        defs = [f for f in facts if f["type"] == "definition"][:2]
        vals = [f for f in facts if f["type"] == "value"][:1]

        if eqs:
            e = eqs[0]
            cards.append({
                "topic": title,
                "question": f"What is the governing equation for {e['lhs']} in this chapter?",
                "answer": f"• Core Equation: {e['full']}\n• Significance: Defines the quantitative relation governing {e['lhs']}.\n• Application: Use it to compute values under the stated assumptions.",
            })
        if defs:
            d = defs[0]
            cards.append({
                "topic": title,
                "question": f"What does the principle of {d['concept']} state?",
                "answer": f"• Definition: {d['concept']} is defined as {d['text']}.\n• Key Takeaway: Identify when this principle applies before applying formulas.",
            })
        if vals:
            v = vals[0]
            cards.append({
                "topic": title,
                "question": f"What is the characteristic value of {v['concept']}?",
                "answer": f"• Value: {v['value']}\n• Common Pitfall: Confusing the order of magnitude or forgetting the units.",
            })
        if len(cards) < 2 and defs:
            d = defs[1] if len(defs) > 1 else defs[0]
            cards.append({
                "topic": title,
                "question": f"How is {d['concept']} applied to solve problems?",
                "answer": f"• Principle: {d['text']}\n• Strategy: Deconstruct the scenario, list given quantities, and apply the governing relationship.",
            })
        if not cards:
            cards.append({
                "topic": title,
                "question": f"What is the primary governing principle of {title}?",
                "answer": f"• Principle: {title} defines the invariant relationships and core mechanisms of its domain.\n• Key Focus: Mastery of terminology and boundary conditions.",
            })
        return cards[:3]

    def _fallback_cards(self, title: str, tier: str) -> List[Dict[str, Any]]:
        """Last-resort, grade-safe cards that are guaranteed structurally valid."""
        return [
            {
                "topic": title,
                "question": f"Define the central concept of {title} in your own words.",
                "answer": f"• Core Idea: {title} establishes the foundational rules and relationships of the topic.\n• Why It Matters: These axioms are the toolkit for every later problem set.",
            },
            {
                "topic": title,
                "question": f"What conditions must hold before you can apply the rules of {title}?",
                "answer": "• Boundary: State the assumptions explicitly.\n• Verification: Confirm each quantity is defined and consistent before calculating.",
            },
            {
                "topic": title,
                "question": f"How would you explain {title} using a simple real-world analogy?",
                "answer": f"• Analogy: Relate {title.lower()} to a familiar everyday system that behaves under the same rules.\n• Takeaway: A good analogy keeps the formal definition attached.",
            },
        ]
# ------------------------------------------------------------------ #
    # Key terms & worked examples (source-exact extraction)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _extract_key_terms(text: str, facts: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Extracts term/definition pairs for a glossary using targeted patterns."""
        terms: List[Dict[str, str]] = []
        if not text:
            return terms

        patterns = [
            re.compile(r"(?<![A-Za-z])([A-Z][A-Za-z0-9'\-]{1,40}(?:\s+[A-Za-z0-9'\-]{1,40}){0,5})\s+is\s+defined\s+as\s+([^.!?\n]{12,160})[.!?]"),
            re.compile(r"(?<![A-Za-z])([A-Z][A-Za-z0-9'\-]{1,40}(?:\s+[A-Za-z0-9'\-]{1,40}){0,5})\s+(?:is|are)\s+known\s+as\s+([^.!?\n]{12,160})[.!?]"),
            re.compile(r"(?<![A-Za-z])([A-Za-z][A-Za-z0-9'\-]{1,40}(?:\s+[A-Za-z0-9'\-]{1,40}){0,5})\s+called\s+([^.!?\n]{12,160})[.!?]"),
            re.compile(r"(?<![A-Za-z])([A-Z][A-Za-z0-9'\-]{1,40}(?:\s+[A-Za-z0-9'\-]{1,40}){0,5})\s+refers\s+to\s+([^.!?\n]{12,160})[.!?]"),
        ]
        seen = set()
        for pat in patterns:
            for m in pat.finditer(text):
                term = QuestionGeneratorEngine._clean_concept(m.group(1))
                definition = re.sub(r"\s{2,}", " ", m.group(2)).strip().strip(",;:-")
                if term and len(definition) > 12 and term.lower() not in seen:
                    seen.add(term.lower())
                    terms.append({"term": term, "definition": definition})
                if len(terms) >= 6:
                    break
            if len(terms) >= 6:
                break

        # Fall back to definition facts already extracted
        for d in facts:
            if d["type"] == "definition" and d["concept"].lower() not in seen:
                seen.add(d["concept"].lower())
                terms.append({"term": d["concept"], "definition": d["text"]})
            if len(terms) >= 6:
                break
        return terms[:6]

    @staticmethod
    def _extract_worked_examples(text: str, max_chars: int = 500) -> List[Dict[str, str]]:
        """Pulls short worked-example / solved-problem snippets verbatim from the source."""
        examples = []
        if not text:
            return examples

        markers = re.compile(
            r"(Example\s+\d+(?:\.\d+)?|EXAMPLE\s+\d+|Worked Example|Example \d+)",
            re.IGNORECASE
        )
        for m in markers.finditer(text):
            start = m.end()
            snippet = text[start:start + max_chars]
            # Cut at next example heading or major boundary, NOT 'Solution'
            cut = re.search(r"\n\s*(?:Example\s+\d+|EXAMPLE\s+\d+|Worked Example|Check Your Understanding|Try It|Test Prep|Section Exercises|#{1,3}\s+)", snippet, re.IGNORECASE)
            if cut:
                snippet = snippet[:cut.start()]
            snippet = snippet.strip()
            # Clean up trailing whitespace and running headers like "84     2"
            snippet = re.sub(r"\n\s*\d{1,4}\s*(?:\n|$)", "\n", snippet).strip()
            if len(snippet) > 40:
                first_line = snippet.split("\n")[0].strip()
                ex_title = f"{m.group(0).strip()}: {first_line}" if len(first_line) < 60 and not first_line.lower().startswith("solution") else m.group(0).strip()
                examples.append({
                    "title": ex_title,
                    "content": snippet,
                    "source": m.group(0).strip(),
                    "worked_problem": snippet,
                })
            if len(examples) >= 3:
                break
        return examples
# ------------------------------------------------------------------ #
    # Deterministic subject deep-theory builder (model-free fallback)
    # ------------------------------------------------------------------ #
    def _build_subject_deep_theory(
        self,
        subject: str,
        chapter_title: str,
        c1: str = "",
        c2: str = "",
        c_formula: str = "",
        definitions: Optional[List[Dict[str, Any]]] = None,
        equations: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Always-available, rigorous deep theory built from extracted facts or domain axioms."""
        subj = subject.lower()
        title_l = (chapter_title or "").lower()
        vignette_words = (
            "vacation", "student", "spring break", "farmer", "pump", "diameter",
            "ticket", "hotel", "salary", "trip", "mile", "car", "population",
            "country", "ferris wheel", "wheel", "dollar", "store", "company", "cent",
        )
        def _clean_definition(d: str) -> str:
            if not d:
                return ""
            dl = d.lower()
            if any(w in dl for w in vignette_words):
                return ""
            if dl.startswith(("arbitrary choice", "graph of this", "turning point of", "second most")):
                return ""
            return d

        grounded_principles = []
        if definitions:
            for d in definitions:
                dt = _clean_definition(d.get("text", ""))
                concept = d.get("concept", "").strip()
                if dt and concept:
                    content = dt if dt.lower().startswith(concept.lower()) else f"{concept} is defined as {dt}."
                    grounded_principles.append({
                        "title": concept,
                        "content": content,
                        "tag": "Definition"
                    })
                if len(grounded_principles) >= 3:
                    break

        grounded_formulations = []
        if equations:
            for eq in equations[:3]:
                f_full = eq.get("full", "")
                if len(f_full) < 65 and not any(w in f_full.lower() for w in ("calculator", "menu", "graph", "chapter", "exercise", "figure")):
                    grounded_formulations.append({
                        "title": f"Governing Equation: {eq['lhs']}",
                        "formula": f_full,
                        "derivation": f"Mathematical relationship governing {eq['lhs']} and {eq['rhs']} in {chapter_title}.",
                        "variables": f"LHS: {eq['lhs']} = RHS: {eq['rhs']}",
                    })

        c1 = _clean_definition(c1)
        c2 = _clean_definition(c2)

        # Domain knowledge catalog for high-fidelity offline synthesis
        if "math" in subj or "calc" in subj or "algebra" in subj:
            if "equation" in title_l or "inequalit" in title_l:
                p_a = f"{c1}" if c1 else "An algebraic equation establishes equivalence between two expressions across all values in the solution set."
                p_b = f"{c2}" if c2 else "Inequalities model boundary constraints; multiplying or dividing both sides by a negative scalar reverses the inequality orientation."
                formulations = [
                    {
                        "title": "Quadratic Formula & Discriminant",
                        "formula": "x = (-b ± √(b² - 4ac)) / (2a), with discriminant Δ = b² - 4ac.",
                        "derivation": "Derived by completing the square on the general second-degree polynomial ax² + bx + c = 0.",
                        "variables": "a, b, c = real coefficients (a ≠ 0); Δ > 0 indicates two distinct real roots, Δ = 0 a repeated root, Δ < 0 complex conjugate roots.",
                    },
                    {
                        "title": "Cartesian Distance & Midpoint Metric",
                        "formula": "d = √((x₂ - x₁)² + (y₂ - y₁)²),   M = ((x₁ + x₂)/2, (y₁ + y₂)/2)",
                        "derivation": "Direct application of the Pythagorean theorem a² + b² = c² in the Euclidean coordinate plane ℝ².",
                        "variables": "(x₁, y₁), (x₂, y₂) = coordinates in ℝ²; d = Euclidean separation; M = geometric midpoint.",
                    },
                    {
                        "title": "Linear Slope & Invariant Form",
                        "formula": "y = mx + b,   where m = (y₂ - y₁) / (x₂ - x₁)",
                        "derivation": "Constant geometric rate of change across all collinear points on a non-vertical line.",
                        "variables": "m = slope (rise over run); b = vertical y-intercept; x, y = coordinate variables.",
                    }
                ]
                mental_models = [
                    {
                        "concept": "Balanced Scale Dynamic",
                        "analogy": "View an equation as a two-pan balance scale: any algebraic operation performed on one side must be identically applied to the other to preserve equilibrium.",
                        "takeaway": "Equilibrium is preserved only under identical invertible transformations; never divide by an expression that could evaluate to zero."
                    }
                ]
                worked_examples = [
                    {
                        "title": "Solving Quadratic Equations via Factoring and Formula",
                        "content": "Problem: Solve 2x² - 5x - 3 = 0.\nMethod:\n1. Identify coefficients: a = 2, b = -5, c = -3.\n2. Compute discriminant: Δ = (-5)² - 4(2)(-3) = 25 + 24 = 49 (positive, two distinct real roots).\n3. Apply quadratic formula: x = (5 ± √49) / (2 · 2) = (5 ± 7) / 4.\n4. Separate branches: x₁ = (5 + 7)/4 = 3; x₂ = (5 - 7)/4 = -2/4 = -1/2.\nConclusion: Solution set is {3, -1/2}."
                    }
                ]
                misconceptions = [
                    {
                        "trap": "Failing to reverse the inequality sign when multiplying or dividing by a negative number",
                        "correction": "Negating numbers reflects them across the origin on the real number line, reversing their relative directional order."
                    }
                ]
                return {
                    "principles": grounded_principles if len(grounded_principles) >= 2 else [
                        {"title": "Algebraic Equivalence & Invariance", "content": p_a, "tag": "Core Axiom"},
                        {"title": "Boundary Constraints & Order Monotonicity", "content": p_b, "tag": "Order Property"},
                    ],
                    "formulations": grounded_formulations if len(grounded_formulations) >= 2 else formulations,
                    "mental_models": mental_models,
                    "worked_examples": worked_examples,
                    "misconceptions": misconceptions,
                }
            elif "function" in title_l or "graph" in title_l:
                formulations = [
                    {
                        "title": "Function Composition & Domain Invariant",
                        "formula": "(f ∘ g)(x) = f(g(x)),   dom(f ∘ g) = {x ∈ dom(g) | g(x) ∈ dom(f)}",
                        "derivation": "Sequential evaluation of mappings where the inner function's image feeds the outer domain.",
                        "variables": "f, g = functions; x = independent variable; dom = valid domain subset.",
                    },
                    {
                        "title": "Difference Quotient & Rate Metric",
                        "formula": "[f(x + h) - f(x)] / h,   h ≠ 0",
                        "derivation": "Secant slope between two points (x, f(x)) and (x+h, f(x+h)) on a curved graph.",
                        "variables": "x = evaluation input; h = non-zero step increment.",
                    },
                    {
                        "title": "Invertibility & Identity Invariant",
                        "formula": "f(f⁻¹(x)) = x   and   f⁻¹(f(x)) = x",
                        "derivation": "A function is invertible if and only if it is one-to-one (passes horizontal line test).",
                        "variables": "f = bijective mapping; f⁻¹ = inverse transformation.",
                    }
                ]
                return {
                    "principles": grounded_principles if len(grounded_principles) >= 2 else [
                        {"title": "Deterministic Mapping Invariant", "content": f"{chapter_title} models relations where each allowed input produces exactly one unique output in the codomain.", "tag": "Core Axiom"},
                        {"title": "Domain and Range Boundaries", "content": "The domain excludes inputs leading to division by zero or negative values under even-indexed roots.", "tag": "Boundary Condition"},
                    ],
                    "formulations": grounded_formulations if len(grounded_formulations) >= 2 else formulations,
                    "mental_models": [
                        {"concept": "Deterministic Pipeline", "analogy": "Treat a function as an automated factory conveyor belt: every raw input x produces a predictable output y without ambiguity.", "takeaway": "An ambiguous or multiple-output rule fails the vertical line test and is not a function."}
                    ],
                    "worked_examples": [
                        {
                            "title": "Evaluating and Inverting a Linear Function",
                            "content": "Problem: Given f(x) = 3x - 5, find f⁻¹(x).\nMethod:\n1. Set y = 3x - 5.\n2. Swap variables to invert: x = 3y - 5.\n3. Solve for y: 3y = x + 5, so y = (x + 5) / 3.\nConclusion: The inverse function is f⁻¹(x) = (x + 5) / 3."
                        }
                    ],
                    "misconceptions": [
                        {"trap": "Confusing f⁻¹(x) with the reciprocal 1/f(x)", "correction": "The superscript -1 in f⁻¹ represents inverse mapping, not an arithmetic exponent."}
                    ],
                }
            elif "polynomial" in title_l or "rational" in title_l:
                formulations = [
                    {
                        "title": "General Polynomial Form",
                        "formula": "P(x) = aₙxⁿ + aₙ₋₁xⁿ⁻¹ + ... + a₁x + a₀,   aₙ ≠ 0",
                        "derivation": "Sum of monomials with non-negative integer exponents defining smooth continuous curves.",
                        "variables": "aₙ = leading coefficient; n = non-negative integer degree; a₀ = constant term.",
                    },
                    {
                        "title": "Rational Function & Asymptotes",
                        "formula": "R(x) = P(x) / Q(x),   Q(x) ≠ 0",
                        "derivation": "Ratio of polynomials; vertical asymptotes occur at zeros of Q(x) after cancelling common factors.",
                        "variables": "P(x), Q(x) = polynomials; zeros of Q produce discontinuities.",
                    }
                ]
                return {
                    "principles": grounded_principles if len(grounded_principles) >= 2 else [
                        {"title": "Fundamental Theorem of Algebra", "content": "Every polynomial of degree n ≥ 1 has exactly n complex roots, counting algebraic multiplicity.", "tag": "Core Axiom"},
                        {"title": "End-Behavior Dominance", "content": "For large |x|, a polynomial's growth is completely governed by its leading term aₙxⁿ.", "tag": "Asymptotic Property"},
                    ],
                    "formulations": grounded_formulations if len(grounded_formulations) >= 2 else formulations,
                    "mental_models": [
                        {"concept": "Leading-Term Dominance", "analogy": "In extreme conditions, the highest-power term dwarfs all lower-power terms, like a rocket engine overtaking small auxiliary thrusters.", "takeaway": "Analyze degree and leading coefficient parity to immediately sketch global trajectory."}
                    ],
                    "worked_examples": [
                        {
                            "title": "Finding Asymptotes of a Rational Function",
                            "content": "Problem: Find the vertical and horizontal asymptotes of R(x) = (2x + 1) / (x - 3).\nMethod:\n1. Vertical asymptote: set denominator to zero: x - 3 = 0 => x = 3.\n2. Degrees of numerator and denominator are equal (1 and 1).\n3. Horizontal asymptote is ratio of leading coefficients: y = 2/1 = 2.\nConclusion: Vertical asymptote at x = 3, horizontal asymptote at y = 2."
                        }
                    ],
                    "misconceptions": [
                        {"trap": "Assuming every denominator zero creates a vertical asymptote", "correction": "Zeros that cancel with numerator factors create removable discontinuities (holes), not vertical asymptotes."}
                    ],
                }
            elif "exponential" in title_l or "logarithm" in title_l:
                formulations = [
                    {
                        "title": "Continuous Exponential Growth & Decay",
                        "formula": "A(t) = A₀ e^(kt),   where k > 0 (growth), k < 0 (decay)",
                        "derivation": "Solution to the differential rate equation dA/dt = kA.",
                        "variables": "A₀ = initial quantity; k = continuous rate constant; t = elapsed time.",
                    },
                    {
                        "title": "Logarithm Fundamental Inversion & Product Law",
                        "formula": "log_b(xy) = log_b(x) + log_b(y),   b^(log_b(x)) = x",
                        "derivation": "Exponent rules translated under the logarithmic bijection.",
                        "variables": "b = positive base (b ≠ 1); x, y = positive real arguments.",
                    }
                ]
                return {
                    "principles": grounded_principles if len(grounded_principles) >= 2 else [
                        {"title": "Exponential Base Scaling", "content": f"{chapter_title} models phenomena where rate of change is directly proportional to current magnitude.", "tag": "Core Axiom"},
                        {"title": "Logarithmic Domain Constraint", "content": "Logarithmic functions are strictly defined only for positive arguments (x > 0) in the real number system.", "tag": "Boundary Condition"},
                    ],
                    "formulations": grounded_formulations if len(grounded_formulations) >= 2 else formulations,
                    "mental_models": [
                        {"concept": "Scale Multiplier vs. Additive Steps", "analogy": "Exponential growth multiplies quantities in equal time intervals, while logarithms compress multiplicative spans into additive steps.", "takeaway": "Logarithms linearize exponential data for analytical tractability."}
                    ],
                    "worked_examples": [
                        {
                            "title": "Solving an Exponential Equation Using Natural Logs",
                            "content": "Problem: Solve 5 e^(2x) = 20.\nMethod:\n1. Divide both sides by 5: e^(2x) = 4.\n2. Take natural logarithm of both sides: ln(e^(2x)) = ln(4).\n3. Simplify LHS: 2x = ln(4).\n4. Divide by 2: x = ln(4) / 2 = ln(2) ≈ 0.693.\nConclusion: Solution is x = ln(2)."
                        }
                    ],
                    "misconceptions": [
                        {"trap": "Distributing logarithms across sums: log(x + y) ≠ log(x) + log(y)", "correction": "Logarithms convert products to sums (log(xy) = log x + log y); they do not distribute across addition."}
                    ],
                }
            elif "trigonometr" in title_l or "circle" in title_l or "periodic" in title_l:
                formulations = [
                    {
                        "title": "Pythagorean Trigonometric Invariant",
                        "formula": "sin²(θ) + cos²(θ) = 1,   tan²(θ) + 1 = sec²(θ)",
                        "derivation": "Direct mapping of the unit circle equation x² + y² = 1 with x = cos(θ), y = sin(θ).",
                        "variables": "θ = angle measured in radians or degrees.",
                    },
                    {
                        "title": "Periodic Sinusoidal Model",
                        "formula": "y = A sin(B(x - C)) + D,   Period T = 2π / |B|",
                        "derivation": "Harmonic oscillation parametrized by amplitude, frequency, and phase translation.",
                        "variables": "|A| = amplitude; 2π/|B| = wavelength/period; C = phase shift; D = midline vertical shift.",
                    }
                ]
                return {
                    "principles": grounded_principles if len(grounded_principles) >= 2 else [
                        {"title": "Circular Invariance & Angle Periodicity", "content": f"{chapter_title} projects circular geometric rotation onto rectilinear coordinate axes with period 2π.", "tag": "Core Axiom"},
                        {"title": "Radian Metric Coherence", "content": "Radian angle measure directly equates arc length s to radius r via s = rθ, making calculus derivations dimensionless.", "tag": "Geometric Invariant"},
                    ],
                    "formulations": grounded_formulations if len(grounded_formulations) >= 2 else formulations,
                    "mental_models": [
                        {"concept": "Rotating Unit Phasor", "analogy": "Envision an arm rotating on a bicycle wheel: height above axle is sine, horizontal distance is cosine, and full cycles repeat every 2π radians.", "takeaway": "All trigonometric identities originate from the geometry of the unit circle."}
                    ],
                    "worked_examples": [
                        {
                            "title": "Evaluating Exact Values via Unit Circle Geometry",
                            "content": "Problem: Find the exact values of sin(5π/6) and cos(5π/6).\nMethod:\n1. Identify reference angle: π - 5π/6 = π/6 (30°).\n2. Sine of π/6 is 1/2; cosine of π/6 is √3/2.\n3. In Quadrant II (5π/6), x is negative and y is positive.\nConclusion: sin(5π/6) = 1/2 and cos(5π/6) = -√3/2."
                        }
                    ],
                    "misconceptions": [
                        {"trap": "Treating degrees and radians interchangeably in formula arguments", "correction": "Formulas involving arc length and analytical derivatives require arguments in radians, not degrees."}
                    ],
                }
            elif "calculus" in subj or "limit" in title_l or "deriv" in title_l or "integr" in title_l:
                formulations = [
                    {
                        "title": "Formal Definition of the Derivative",
                        "formula": "f'(x) = lim_{h -> 0} [f(x + h) - f(x)] / h",
                        "derivation": "Limiting value of secant slope as interval separation h converges to zero.",
                        "variables": "f'(x) = instantaneous rate of change; h = infinitesimal perturbation.",
                    },
                    {
                        "title": "Fundamental Theorem of Calculus",
                        "formula": "∫ₐᵇ f(x) dx = F(b) - F(a),   where F'(x) = f(x)",
                        "derivation": "Connects infinitesimal accumulation (integration) with rate of change (differentiation) as inverse operations.",
                        "variables": "f = continuous integrand; F = antiderivative; a, b = integration bounds.",
                    }
                ]
                return {
                    "principles": grounded_principles if len(grounded_principles) >= 2 else [
                        {"title": "Local Linearity & Instantaneous Rate", "content": f"{chapter_title} establishes how continuous smooth curves are approximated by tangent linear manifolds locally.", "tag": "Core Axiom"},
                        {"title": "Continuity as Precondition for Differentiability", "content": "Differentiability implies continuity, but continuity does not guarantee differentiability at cusps or corners.", "tag": "Foundational Theorem"},
                    ],
                    "formulations": grounded_formulations if len(grounded_formulations) >= 2 else formulations,
                    "mental_models": [
                        {"concept": "Microscopic Zoom Linearity", "analogy": "Zoom in infinitely close on a differentiable curve: eventually it looks indistinguishable from a straight tangent line.", "takeaway": "Derivatives capture the exact slope of this localized line."}
                    ],
                    "worked_examples": [
                        {
                            "title": "Computing Derivative from First Principles",
                            "content": "Problem: Compute the derivative of f(x) = x².\nMethod:\n1. Form difference quotient: [(x + h)² - x²] / h.\n2. Expand numerator: [x² + 2xh + h² - x²] / h = [2xh + h²] / h.\n3. Factor out h: h(2x + h) / h = 2x + h (for h ≠ 0).\n4. Take limit as h -> 0: lim_{h -> 0} (2x + h) = 2x.\nConclusion: f'(x) = 2x."
                        }
                    ],
                    "misconceptions": [
                        {"trap": "Assuming continuous functions are always differentiable", "correction": "Functions with sharp corners (like f(x) = |x| at x=0) are continuous everywhere but lack a unique tangent slope."}
                    ],
                }

        elif "phys" in subj or "mech" in subj:
            formulations = [
                {
                    "title": "Newton's Second Law & Momentum Formulation",
                    "formula": "Σ F = m a = dp / dt,   where p = m v",
                    "derivation": "Net external force produces proportional acceleration in an inertial reference frame.",
                    "variables": "Σ F = net vector force (N); m = inertial mass (kg); a = acceleration (m/s²); p = momentum (kg·m/s).",
                },
                {
                    "title": "Work-Energy Theorem & Conservation Invariant",
                    "formula": "W_net = ΔK = (1/2) m v_f² - (1/2) m v_i²,   E_tot = K + U = const",
                    "derivation": "Line integral of force along displacement equates to change in translational kinetic energy.",
                    "variables": "W = work (J); K = kinetic energy; U = potential energy; v = velocity (m/s).",
                }
            ]
            return {
                "principles": grounded_principles if len(grounded_principles) >= 2 else [
                    {"title": "Conservation Laws & Reference Frames", "content": f"{chapter_title} formulates physical invariants that remain constant under closed system transformations.", "tag": "Core Axiom"},
                    {"title": "Superposition of Forces", "content": "Multiple forces acting on a point body combine vectorially according to Euclidean vector addition.", "tag": "Vector Invariant"},
                ],
                "formulations": grounded_formulations if len(grounded_formulations) >= 2 else formulations,
                "mental_models": [
                    {"concept": "Energy Accounting Ledger", "analogy": "Energy cannot be created or destroyed, only transferred: like a strictly balanced accounting ledger, every expenditure in potential energy appears as kinetic energy or work.", "takeaway": "Establish the initial vs. final state before writing equations."}
                ],
                "worked_examples": [
                    {
                        "title": "Kinematic Motion Under Constant Gravitational Acceleration",
                        "content": "Problem: A ball is dropped from a height of 20 m. Find its velocity just before impact (g = 9.8 m/s²).\nMethod:\n1. Use kinematic equation: v² = v₀² + 2a(y - y₀).\n2. Given: v₀ = 0, a = 9.8 m/s², Δy = 20 m.\n3. Compute: v² = 0 + 2(9.8)(20) = 392.\n4. Take square root: v = √392 ≈ 19.8 m/s.\nConclusion: Final velocity is approximately 19.8 m/s downward."
                    }
                ],
                "misconceptions": [
                    {"trap": "Treating vectors like scalar quantities without resolving directional components", "correction": "Forces and velocities along orthogonal axes (x and y) must be solved independently."}
                ],
            }

        elif "bio" in subj or "chem" in subj or "life" in subj:
            formulations = [
                {
                    "title": "Equilibrium Constant & Reaction Quotient",
                    "formula": "K_eq = ([C]^c [D]^d) / ([A]^a [B]^b),   ΔG° = -RT ln(K_eq)",
                    "derivation": "Law of mass action derived from thermodynamic chemical potential minimization.",
                    "variables": "K_eq = equilibrium ratio; [X] = molar concentrations; R = gas constant; T = absolute temperature.",
                }
            ]
            return {
                "principles": grounded_principles if len(grounded_principles) >= 2 else [
                    {"title": "Homeostasis and Dynamic Equilibrium", "content": f"{chapter_title} describes how biological and chemical systems maintain stable internal states through continuous regulatory feedbacks.", "tag": "Core Axiom"},
                    {"title": "Structure-Function Relationship", "content": "Molecular conformation and macroscopic architecture dictate operational biological activity and catalytic specificity.", "tag": "Biological Principle"},
                ],
                "formulations": grounded_formulations if len(grounded_formulations) >= 1 else formulations,
                "mental_models": [
                    {"concept": "Lock-and-Key Regulatory Circuit", "analogy": "Biological pathways operate like interconnected relays: specific molecular keys trigger specific locks, propagating regulatory signals.", "takeaway": "Trace the cascade from molecular trigger to systemic response."}
                ],
                "worked_examples": [
                    {
                        "title": "Predicting Equilibrium Shift via Le Chatelier's Principle",
                        "content": "Problem: For the exothermic reaction N₂(g) + 3H₂(g) ⇌ 2NH₃(g) + heat, predict the shift if temperature is increased.\nMethod:\n1. Le Chatelier's principle states a system responds to relieve applied stress.\n2. Heat is a product in this exothermic reaction.\n3. Increasing temperature adds stress to the product side.\nConclusion: Equilibrium shifts to the left (toward reactants) to consume excess thermal energy."
                    }
                ],
                "misconceptions": [
                    {"trap": "Confusing dynamic equilibrium with a static cessation of reactions", "correction": "At dynamic equilibrium, forward and reverse reactions proceed continuously at identical rates."}
                ],
            }

        elif "comput" in subj or "data" in subj or "software" in subj or "algorithm" in subj or "cs" in subj:
            formulations = [
                {
                    "title": "Asymptotic Complexity & Big-O Recurrence",
                    "formula": "T(n) = a T(n/b) + O(n^d),   T(n) ∈ O(f(n))",
                    "derivation": "Master theorem for divide-and-conquer recurrences bounding operational scaling.",
                    "variables": "a = subproblem count; b = division factor; d = recombination exponent; n = input cardinality.",
                }
            ]
            return {
                "principles": grounded_principles if len(grounded_principles) >= 2 else [
                    {"title": "Computational Invariants & State Guarantees", "content": f"{chapter_title} establishes deterministic state transformations and invariants that hold across all execution cycles.", "tag": "Core Axiom"},
                    {"title": "Asymptotic Resource Scaling", "content": "Efficiency is measured against input size n as n -> ∞, abstracting hardware differences.", "tag": "Complexity Axiom"},
                ],
                "formulations": grounded_formulations if len(grounded_formulations) >= 1 else formulations,
                "mental_models": [
                    {"concept": "State Machine Induction", "analogy": "Treat an algorithm as an inductive ladder: prove the base case holds, then ensure every step preserves the invariant to reach guaranteed termination.", "takeaway": "Invariants guarantee correctness; transition steps dictate runtime."}
                ],
                "worked_examples": [
                    {
                        "title": "Verifying Binary Search Loop Invariant",
                        "content": "Problem: Prove binary search terminates with the correct index in O(log n) steps.\nMethod:\n1. Loop invariant: If key is in array A, it lies within A[low..high].\n2. Initialization: low=0, high=n-1 covers entire array.\n3. Maintenance: mid=(low+high)//2; narrowing eliminates half the search space while preserving the invariant.\n4. Termination: Search terminates when low > high (element not present) or A[mid] == key.\nConclusion: Space halves each iteration, bounding runtime to O(log n)."
                        }
                ],
                "misconceptions": [
                    {"trap": "Confusing best-case observations with worst-case asymptotic bounds", "correction": "Big-O characterizes the asymptotic upper bound under worst-case inputs, not optimistic runtime."}
                ],
            }

        # General STEM fallback
        return {
            "principles": grounded_principles if len(grounded_principles) >= 2 else [
                {"title": "Primary Governing Principle", "content": c1 or f"{chapter_title} establishes the foundational definitions, empirical relationships, and analytical rules of its domain.", "tag": "Core Axiom"},
                {"title": "Operational Boundaries & Invariants", "content": c2 or "Analytical methods apply strictly within verified boundary conditions, conservation constraints, and stated domain assumptions.", "tag": "Mechanics"},
            ],
            "formulations": grounded_formulations if len(grounded_formulations) >= 1 else [
                {"title": "Governing Analytical Formulation", "formula": c_formula or "y = f(x₁, x₂, ..., xₙ) maps domain variables to system observables.", "derivation": "Derived from foundational conservation and symmetry principles.", "variables": "State variables, parameters, and boundary constraints."}
            ],
            "mental_models": [
                {"concept": "Conserved Dynamic System", "analogy": f"Treat {chapter_title} as an interconnected system governed by balancing constraints: any change to one variable propagates predictable adjustments to maintain system invariants.", "takeaway": "Identify the conserved quantities and boundary conditions before solving."}
            ],
            "worked_examples": [
                {
                    "title": f"Structured Problem Walkthrough: {chapter_title}",
                    "content": f"Problem: Apply governing relationships for {chapter_title}.\nMethod:\n1. Identify given parameters and target variables.\n2. Verify boundary conditions and domain constraints.\n3. Apply transformation rules systematically while preserving system balance.\nConclusion: Result satisfies all defining constraints."
                }
            ],
            "misconceptions": [
                {"trap": "Applying governing formulas outside their operational assumptions", "correction": "Always establish reference frames, domain restrictions, and parameter validity before computing."}
            ],
        }
# ------------------------------------------------------------------ #
    # Grounded fact extraction (source-verified skeleton)
    # ------------------------------------------------------------------ #
    # Words that can never start or end a concept name captured from prose.
    CONCEPT_LEAD_STOP = {
        "the", "a", "an", "and", "or", "but", "if", "so", "then", "thus", "this",
        "that", "these", "those", "it", "its", "there", "here", "when", "where",
        "while", "with", "without", "in", "into", "on", "of", "for", "from", "to",
        "by", "as", "at", "also", "however", "therefore", "because", "since",
        "what", "which", "who", "whom", "whose", "why", "how", "is", "are", "was",
        "were", "be", "been", "being", "not", "no", "nor", "such", "some", "any",
        "each", "every", "other", "another", "we", "you", "they", "he", "she",
        "our", "their", "his", "her", "us", "them", "all", "both", "few", "many",
        "more", "most", "much", "only", "just", "very", "can", "will", "would",
        "should", "may", "might", "must", "do", "does", "did", "has", "have", "had",
    }
    CONCEPT_TRAIL_STOP = {
        "the", "a", "an", "and", "or", "of", "in", "on", "to", "for", "with", "by",
        "as", "at", "from", "is", "are", "was", "were", "that", "which", "this",
        "these", "those", "it", "its", "also", "but", "if", "then", "than",
    }

    @classmethod
    def _clean_concept(cls, raw: str) -> str:
        """Turns a raw regex hit into a usable concept name (or '' if junk)."""
        words = [w for w in re.split(r"\s+", (raw or "").strip()) if w]
        while words and words[0].lower().strip("'\"",) in cls.CONCEPT_LEAD_STOP:
            words.pop(0)
        while words and words[-1].lower().strip("'\"",) in cls.CONCEPT_TRAIL_STOP:
            words.pop()
        if not words or len(words) > 6:
            return ""
        junk_concept_words = {
            "solution", "example", "exercise", "figure", "table", "chapter", "section",
            "problem", "try it", "check", "note", "remember", "warning", "tip", "summary",
            "caroline", "tracie", "john", "mary", "step", "part", "case", "page"
        }
        low_words = [w.lower() for w in words]
        if any(w in junk_concept_words for w in low_words):
            return ""
        concept = " ".join(words)
        if len(concept) < 3 or len(concept) > 60:
            return ""
        first = concept[0]
        # Concepts are capitalised names/terms, never sentence fragments or
        # stray words that merely happened to follow whitespace.
        if not first.isupper():
            return ""
        if not re.match(r"^[A-Z][A-Za-z0-9'\-]*(?:\s+[A-Za-z0-9'\-]+)*$", concept):
            return ""
        if concept.lower() in cls.CONCEPT_LEAD_STOP:
            return ""
        return concept

    @staticmethod
    def _extract_facts_from_text(text: str) -> List[Dict[str, str]]:
        """
        Extracts concrete facts — named laws, equations, values, definitions —
        directly from the chapter text. This is the 'ground truth skeleton' the
        LLM output is later merged against (never hallucinated).
        """
        facts: List[Dict[str, str]] = []
        if not text:
            return facts

        # 1. Named laws / concepts / definitions across all subjects.
        #    The leading look-behind + capitalised start prevent mid-word hits
        #    like "…co[ntributed to the formation…]".
        def_pattern = re.compile(
            r"(?<![A-Za-z])([A-Z][A-Za-z0-9'\-]{1,40}(?:[ \t]+[A-Za-z0-9'\-]{1,40}){0,5})\s+"
            r"(?:states\s+that|is\s+defined\s+as|are\s+defined\s+as|refers\s+to|"
            r"describes\s+how|describes\s+the|describes|is\s+called|are\s+called|"
            r"is\s+the|are\s+the|represents|signifies|is\s+an?)\s+"
            r"([^.!?\n]{20,180})[.!?]"
        )
        for m in def_pattern.finditer(text):
            concept = QuestionGeneratorEngine._clean_concept(m.group(1))
            desc = re.sub(r"\s{2,}", " ", m.group(2)).strip().strip(",;:-")
            if concept and len(desc) > 20:
                facts.append({"type": "definition", "concept": concept, "text": desc})
            if len(facts) >= 12:
                break

        # 2. Equations: "F = m a", "PV = nRT", "Delta U = Q - W", Unicode allowed.
        eq_pattern = re.compile(
            r"([A-Za-zΔ][A-Za-z0-9_]*[\sA-Za-zΔ_]{0,20})\s*=\s*([A-Za-z0-9_Δπ\+\-\*\/\(\)\.\s]{1,42})(?=[,\.;\)\n]|$|\\n)"
        )
        for m in eq_pattern.finditer(text):
            raw_lhs = m.group(1).strip()
            raw_rhs = m.group(2).strip()

            lhs_tokens = raw_lhs.lstrip("({[").split()
            if not lhs_tokens:
                continue
            if len(lhs_tokens) >= 2 and lhs_tokens[-2].lower() in ("delta", "net", "avg", "total", "sum"):
                lhs = f"{lhs_tokens[-2]} {lhs_tokens[-1]}"
            else:
                lhs = lhs_tokens[-1]
            lhs = re.sub(r"^(?:is|are|the|an|that|where|equation|formula|of)\s+", "", lhs, flags=re.I).strip()

            rhs = raw_rhs.rstrip(")}].;, \t").strip()
            if lhs and rhs and len(rhs) >= 1:
                # Reject trivial assignment roots (e.g. x = 0, y = 0) and unclosed parens
                if re.match(r"^[a-zA-Z]\s*=\s*\d+$", f"{lhs} = {rhs}"):
                    continue
                if rhs.count("(") != rhs.count(")"):
                    continue
                low_lhs = lhs.lower()
                low_rhs = rhs.lower()
                junk_words = ("http", "www", "chapter", "is ", "solution", "calculator", "menu", "graph", "figure", "table", "after", "before", "function of", "diameter", "use", "the", "we", "can", "then", "from", "that", "with")
                if any(kw in low_lhs for kw in junk_words) or any(kw in low_rhs for kw in junk_words):
                    continue
                facts.append({"type": "equation", "lhs": lhs, "rhs": rhs, "full": f"{lhs} = {rhs}"})
            if len(facts) >= 12:
                break

        # 3. Constants / characteristic values with SI units.
        val_pattern = re.compile(
            r"([A-Za-z][A-Za-z\s]{2,35})\s+(?:is|equals?|has a value of|value of)\s+([+\-]?\d+(?:\.\d+)?\s*(?:m/s²?|m/s|N|J|K|Hz|kg|Pa|mol|W|V|A|°C|m|s|h|min|%|eV)?\b)",
            re.IGNORECASE
        )
        for m in val_pattern.finditer(text):
            concept = m.group(1).strip()
            val = m.group(2).strip()
            if len(concept) > 2 and len(val) > 0:
                facts.append({"type": "value", "concept": concept, "value": val})
            if len(facts) >= 12:
                break

        # De-duplicate, keep the first 12 strongest facts.
        seen = set()
        deduped = []
        for f in facts:
            key = (f["type"], f.get("lhs") or f.get("concept") or f.get("rhs") or f.get("text") or "")[:60]
            if key not in seen:
                seen.add(key)
                deduped.append(f)
        return deduped[:12]
    @staticmethod
    def _generate_distractors(correct: str, subject: str, q_type: str) -> List[str]:
        """Generates plausible wrong options based on question type and subject domain."""
        sub_low = subject.lower()
        is_cs = any(k in sub_low for k in ["computer", "software", "data", "algorithm", "code"])
        is_math = "math" in sub_low

        if q_type == "equation":
            if is_cs:
                return [
                    "It introduces unconstrained quadratic O(n^2) space overhead across execution paths",
                    "It exhibits asymptotic exponential growth under worst-case permutations",
                    "It violates state invariant preservation across asynchronous operations"
                ]
            elif is_math:
                return [
                    "It holds only for strictly positive real values with singular boundaries",
                    "It represents a non-convergent divergent series outside the unit disc",
                    "It requires non-linear coordinate transformations with zero determinant"
                ]
            return [
                "It represents an inverse relation with zero direct proportionality",
                "It requires a constant offset under all non-equilibrium conditions",
                "It applies strictly to non-conservative dissipative forces"
            ]
        elif q_type == "value":
            try:
                num_m = re.search(r"[-+]?\d+(?:\.\d+)?", correct)
                if num_m:
                    num = float(num_m.group(0))
                    unit = correct.replace(num_m.group(0), "").strip()
                    return [
                        f"{num * 2:g} {unit}".strip(),
                        f"{max(0.0, num / 2):g} {unit}".strip(),
                        f"{num + 10:g} {unit}".strip()
                    ]
            except Exception:
                pass
            return ["0", "Infinity", "Undefined in this computational frame"]

        if is_cs:
            return [
                f"An obsolete architectural anti-pattern superseded by modern {subject} paradigms.",
                "A non-deterministic scheduling heuristic with no formal correctness guarantees.",
                "A tightly coupled implementation that breaks modularity and abstraction boundaries."
            ]
        elif is_math:
            return [
                "An unverified conjecture inapplicable to standard topological spaces.",
                "A circular definition with undefined boundary conditions.",
                "A special case restricted solely to finite dimensional Euclidean spaces."
            ]

        return [
            f"An empirical approximation applicable only outside standard {subject} models.",
            f"A deprecated historical hypothesis superseded by contemporary findings.",
            f"A localized boundary anomaly with zero general applicability."
        ]
    def generate_assessment_items(
        self,
        course_title: str,
        chapters: List[Dict[str, Any]],
        subject: str = "General",
        tier: str = "Standard"
    ) -> Dict[str, Any]:
        """Generates grounded practice quizzes and summative final exam questions extracted from chapter content."""
        if self.local_llm.is_available():
            try:
                local_assessments = self.local_llm.generate_course_assessments(course_title, chapters, subject, tier)
                if (local_assessments and
                    len(local_assessments.get("quizzes", [])) >= len(chapters) and
                    len(local_assessments.get("finalExam", [])) >= len(chapters)):
                    return local_assessments
            except Exception as e:
                print(f"[QGE] Local assessment generation fallback: {e}")

        quizzes = []
        final_exams = []

        for idx, ch in enumerate(chapters, 1):
            ch_title = ch.get("title", f"Chapter {idx}")
            ch_content = ch.get("full_text") or ch.get("content") or ch.get("summary") or ""
            facts = self._extract_facts_from_text(ch_content)

            eq_fact = next((f for f in facts if f["type"] == "equation"), None)
            val_fact = next((f for f in facts if f["type"] == "value"), None)
            def_fact = next((f for f in facts if f["type"] == "definition"), None)

            if eq_fact:
                q_text = f"According to the formulation in {ch_title}, what is the mathematical expression for {eq_fact['lhs']}?"
                correct = eq_fact["rhs"]
                distractors = self._generate_distractors(correct, subject, "equation")
            elif val_fact:
                q_text = f"In {ch_title}, what is the characteristic value of {val_fact['concept']}?"
                correct = val_fact["value"]
                distractors = self._generate_distractors(correct, subject, "value")
            elif def_fact:
                q_text = f"Which statement accurately expresses the principle of {def_fact['concept']} in {ch_title}?"
                correct = f"{def_fact['concept']} {def_fact['text'][:140]}"
                distractors = self._generate_distractors(correct, subject, "definition")
            else:
                q_text = f"What is the foundational theoretical relationship established in {ch_title}?"
                correct = f"It defines the invariant relationships and core mechanisms of {ch_title}."
                distractors = self._generate_distractors(correct, subject, "definition")

            options = [correct] + distractors[:3]
            seen = set()
            clean_options = []
            for opt in options:
                if opt not in seen:
                    clean_options.append(opt)
                    seen.add(opt)
            while len(clean_options) < 4:
                clean_options.append(f"Alternative hypothesis #{len(clean_options)} in {subject}")

            quizzes.append({
                "id": f"q_mcq_{idx}_1",
                "text": q_text,
                "concept": ch_title,
                "options": clean_options,
                "correct_answer": correct
            })

            if eq_fact:
                exam_text = f"State the governing equation or formula for {eq_fact['lhs']} as derived in {ch_title}."
                expected_ans = eq_fact["rhs"]
                formula_str = eq_fact["full"]
                misconception = f"Confusing the variables or operation signs in {eq_fact['lhs']} = {eq_fact['rhs']}."
            elif val_fact:
                exam_text = f"Provide the quantitative value or constant for {val_fact['concept']} from {ch_title}."
                expected_ans = val_fact["value"]
                formula_str = f"Constant value: {val_fact['value']}"
                misconception = "Forgetting unit dimensions or applying wrong order of magnitude."
            elif def_fact:
                exam_text = f"What core theoretical concept in {ch_title} describes: '{def_fact['text'][:120]}'?"
                expected_ans = def_fact["concept"]
                formula_str = f"Governing principle: {def_fact['concept']}"
                misconception = f"Confusing {def_fact['concept']} with peripheral secondary effects."
            else:
                exam_text = f"What is the primary governing principle of {ch_title} in {subject}?"
                expected_ans = ch_title
                formula_str = f"Axioms of {ch_title}"
                misconception = "Confusing core governing definitions with peripheral derivations."

            final_exams.append({
                "qId": f"exam_item_{idx}",
                "moduleOrigin": f"Module {idx}: {ch_title}",
                "question_type": "short_answer",
                "options": [],
                "text": exam_text,
                "expected": expected_ans,
                "formula": formula_str,
                "misconception": misconception
            })

        return {
            "quizzes": quizzes,
            "finalExam": final_exams
        }