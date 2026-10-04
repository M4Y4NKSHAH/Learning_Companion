import os
import re
import json
import uuid
from typing import Dict, List, Any, Optional

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
        try:
            return ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                temperature=0.2,
                google_api_key=self.api_key,
                max_retries=1
            )
        except Exception as e:
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
            clean_json = res.content.replace("```json", "").replace("```", "").strip()
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
        )

        cards_out = local_cards if (local_out is not None and local_cards) else None
        if cards_out is None:
            cards_out = self._facts_to_cards(clean_title, facts, subject)

        # --- 4. Ground & merge ------------------------------------------------- #
        deep_theory = self._ground_deep_theory(blueprint, deep_root, equations, definitions)

        # key_terms / worked_examples are always deterministic (source extracted)
        if key_terms:
            deep_theory["key_terms"] = key_terms
        if worked_examples:
            deep_theory["worked_examples"] = worked_examples

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
        try:
            prompt = (
                f"You are an expert curriculum architect for {subject}.\n"
                f"TARGET LEARNER LEVEL: {guardrails['label']} ({guardrails['audience']})\n"
                f"Math/Conceptual Ceiling: {guardrails['math_ceiling']}\n"
                f"STRICT PROHIBITIONS:\n{prohibitions}\n"
                f"MANDATORY REQUIREMENTS:\n{requirements}\n\n"
                f"Chapter {chapter_index}: '{title}'\n"
                f"Source text:\n\"\"\"{text[:3200]}\"\"\"\n\n"
                "Return a JSON object with exactly: summary(string), objectives(array of 3),\n"
                "principles, formulations, mental_models, misconceptions (arrays as before),\n"
                "and cards (array of 3 with topic/question/answer). Respond ONLY with the JSON."
            )
            res = gemini.invoke([HumanMessage(content=prompt)])
            clean_json = res.content.replace("```json", "").replace("```", "").strip()
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

        # Ground formulations with source equations when the LLM omitted/erred.
        if equations:
            grounded_formulas = []
            for f in equations[:3]:
                grounded_formulas.append({
                    "title": f"Equation: {f['lhs']}",
                    "formula": f["full"],
                    "derivation": "Extracted verbatim from the source chapter text.",
                    "variables": f"LHS: {f['lhs']} = RHS: {f['rhs']}",
                })
            if deep.get("formulations"):
                kept = [fm for fm in deep["formulations"] if isinstance(fm, dict) and self._in_text(fm.get("formula", ""), [e["full"] for e in equations])]
                if kept:
                    combined = kept[:2] + grounded_formulas[:1]
                    seen = set()
                    deep["formulations"] = []
                    for fm in combined:
                        key = fm.get("formula", "")
                        if key and key not in seen:
                            seen.add(key)
                            deep["formulations"].append(fm)
                else:
                    deep["formulations"] = grounded_formulas[:2]
            else:
                deep["formulations"] = grounded_formulas[:2]

        # Ground principles with source definitions when absent.
        if definitions and len(deep.get("principles", [])) < 2:
            existing = deep.get("principles", []) or []
            for d in definitions[: (2 - len(existing))]:
                deep.setdefault("principles", []).append({
                    "title": d["concept"],
                    "content": d["text"],
                    "tag": "Definition",
                })

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
        parts = [f"{title} establishes the core theoretical framework of its domain."]
        eqs = [f["full"] for f in facts if f["type"] == "equation"][:2]
        defs = [d["text"] for d in facts if d["type"] == "definition"][:1]
        if defs:
            parts.append(defs[0])
        if eqs:
            parts.append(f"Its governing relations include {' and '.join(eqs)}.")
        if len(parts) < 3:
            parts.append("Mastering the definitions and boundary conditions is essential for applying the framework.")
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
    def _extract_worked_examples(text: str, max_chars: int = 260) -> List[Dict[str, str]]:
        """Pulls short worked-example / solved-problem snippets verbatim from the source."""
        examples = []
        if not text:
            return examples

        markers = re.compile(
            r"(Example\s+\d+(?:\.\d+)?|EXAMPLE\s+\d+|Worked Example|Example \d+|e\.g\.[^.!?]+)",
            re.IGNORECASE
        )
        for m in markers.finditer(text):
            start = m.end()
            snippet = text[start:start + max_chars]
            # Cut at the next likely example/heading boundary
            cut = re.search(r"\n\s*(Example|Solution|Check Your Understanding|Try It|Test Prep|$)", snippet, re.IGNORECASE)
            if cut:
                snippet = snippet[:cut.start()]
            snippet = snippet.strip()
            if len(snippet) > 40:
                examples.append({"source": m.group(0).strip(), "worked_problem": snippet[:max_chars]})
            if len(examples) >= 2:
                break
        return examples
# ------------------------------------------------------------------ #
    # Deterministic subject deep-theory builder (model-free fallback)
    # ------------------------------------------------------------------ #
    def _build_subject_deep_theory(
        self,
        subject: str,
        chapter_title: str,
        c1: str,
        c2: str,
        c_formula: str,
    ) -> Dict[str, Any]:
        """Always-available, grade-neutral deep theory built from extracted facts."""
        subj = subject.lower()

        if "phys" in subj or "mech" in subj:
            principles_a = f"{c1}" if c1 else f"{chapter_title} establishes the fundamental laws governing its domain, defining how measurable quantities relate and interact."
            principles_b = f"{c2}" if c2 else f"{chapter_title} connects idealised models to observed reality through clearly stated assumptions and boundary conditions."
            formulation = c_formula or "The governing equation links the state variables and constants introduced in this chapter."
            return {
                "principles": [
                    {"title": "Primary Governing Principle", "content": principles_a, "tag": "Core Axiom"},
                    {"title": "Operational Domain & Assumptions", "content": principles_b, "tag": "Mechanics"},
                ],
                "formulations": [
                    {"title": "Governing Formulation", "formula": formulation, "derivation": "Derived from foundational conservation and symmetry principles.", "variables": "State variables, proportionalities, and physical boundary constraints."}
                ],
                "mental_models": [
                    {"concept": "Dynamical System Model", "analogy": f"Think of {chapter_title} as a system where every action produces a measurable, rule-bound response.", "takeaway": "Identify the invariants and conserved quantities first."}
                ],
                "misconceptions": [
                    {"trap": "Applying an equation outside its stated assumptions", "correction": "Always establish the operational domain, reference frame, and parameter validity before calculating."}
                ],
            }
        elif "math" in subj or "calc" in subj or "algebra" in subj:
            principles_a = f"{c1}" if c1 else f"{chapter_title} formalises a precise transformation rule connecting mathematical objects."
            principles_b = f"{c2}" if c2 else "The chapter develops the notation, axioms, and procedural steps necessary to apply and invert the rule reliably."
            formulation = c_formula or "The defining rule expresses the relationship between the mathematical entities under study."
            return {
                "principles": [
                    {"title": "Defining Rule", "content": principles_a, "tag": "Core Axiom"},
                    {"title": "Procedural Framework", "content": principles_b, "tag": "Procedure"},
                ],
                "formulations": [
                    {"title": "Core Formulation", "formula": formulation, "derivation": "Derived by applying the defining axioms to the canonical cases.", "variables": "Symbols denote the mathematical objects and operators of the rule."}
                ],
                "mental_models": [
                    {"concept": "Transformation View", "analogy": "Treat the rule as a machine that maps an input expression to a canonical output expression.", "takeaway": "Every rule has an inverse or a boundary — know both."}
                ],
                "misconceptions": [
                    {"trap": "Applying the rule in reverse order or outside its domain", "correction": "Verify preconditions and order of operations before applying any transformation."}
                ],
            }
        elif "bio" in subj or "chem" in subj or "life" in subj:
            principles_a = f"{c1}" if c1 else f"{chapter_title} explains a biological/chemical process through interacting components and pathways."
            principles_b = f"{c2}" if c2 else "Systems-level behavior emerges from the collective action of the individual components described below."
            formulation = c_formula or "The central relationship ties together the quantities that characterise the process."
            return {
                "principles": [
                    {"title": "Governing Process", "content": principles_a, "tag": "Core Axiom"},
                    {"title": "Emergent Behaviour", "content": principles_b, "tag": "System"},
                ],
                "formulations": [
                    {"title": "Central Relationship", "formula": formulation, "derivation": "Observed from controlled experiments and quantitative measurement.", "variables": "Variables represent measurable quantities of the process."}
                ],
                "mental_models": [
                    {"concept": "Pathway Feedback Model", "analogy": f"Understand {chapter_title} as a cascade where each layer regulates the next.", "takeaway": "Trace inputs to outputs and look for feedback loops."}
                ],
                "misconceptions": [
                    {"trap": "Assuming static equilibrium instead of dynamic balance", "correction": "Living systems maintain steady states through continuous input, output, and regulation."}
                ],
            }
        elif "comput" in subj or "data" in subj or "software" in subj or "algorithm" in subj or "cs" in subj:
            principles_a = f"{c1}" if c1 else f"{chapter_title} establishes the fundamental computational principles, formal models of computation, and architectural abstractions that govern data transformations."
            principles_b = f"{c2}" if c2 else "Algorithmic correctness and asymptotic efficiency are derived from structural invariants, boundary termination proofs, and resource guarantees."
            formulation = c_formula or "T(n) = O(f(n)) and S(n) = O(g(n)) governing time and space resource scaling over input cardinality n."
            return {
                "principles": [
                    {"title": "Foundational Computational Paradigm", "content": principles_a, "tag": "Core Axiom"},
                    {"title": "System Invariants & Boundary Guarantees", "content": principles_b, "tag": "Invariant"},
                ],
                "formulations": [
                    {"title": "Algorithmic Complexity & State Bounds", "formula": formulation, "derivation": "Derived from formal recurrences and inductive verification across discrete state transitions.", "variables": "n = problem dimension; T(n) = operation count; S(n) = auxiliary memory allocations."}
                ],
                "mental_models": [
                    {"concept": "State Machine View", "analogy": "Treat the process as a state machine stepping through allowed transitions.", "takeaway": "Invariants guarantee correctness across all state cycles; transition steps determine computational cost."}
                ],
                "worked_examples": [
                    {
                        "title": f"State Transition Analysis: {chapter_title}",
                        "content": f"Problem: Verify structural invariants and boundary conditions for {chapter_title}.\nMethod:\n1. Identify input domain, preconditions, and base cases.\n2. Execute state transitions step-by-step while verifying inductive invariant holds.\n3. Validate termination condition and output post-conditions.\nConclusion: Invariant holds across every cycle, confirming deterministic correctness."
                    }
                ],
                "misconceptions": [
                    {"trap": "Confusing best-case or average-case observations with worst-case asymptotic bounds", "correction": "State the operational domain with respect to adversarial input size and verify boundary conditions before concluding complexity."}
                ],
            }

        # Generic
        return {
            "principles": [
                {"title": "Primary Governing Principle", "content": c1 or f"{chapter_title} establishes the foundational rules and relationships of the topic.", "tag": "Core Axiom"},
                {"title": "Analytical Mechanics", "content": c2 or "Real scenarios are modelled by stating assumptions, identifying quantities, and applying the governing relationship.", "tag": "Mechanics"},
            ],
            "formulations": [
                {"title": "Governing Formulation", "formula": c_formula or "The governing equation links the state variables of the system.", "derivation": "Derived from foundational principles of the domain.", "variables": "State variables and physical boundary constraints."}
            ],
            "mental_models": [
                {"concept": "Conservation & Equilibrium Model", "analogy": f"Think of {chapter_title} as a dynamic system governed by conservation constraints.", "takeaway": "Track invariants, boundary limits, and energy conservation."}
            ],
            "misconceptions": [
                {"trap": "Applying equations outside their operational validity bounds", "correction": "Always establish the operational domain and physical assumptions prior to calculation."}
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
            r"(?<![A-Za-z])([A-Z][A-Za-z0-9'\-]{1,40}(?:\s+[A-Za-z0-9'\-]{1,40}){0,5})\s+"
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
                low = lhs.lower()
                if not any(kw in low for kw in ("http", "www", "chapter", "is ", "solution")):
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