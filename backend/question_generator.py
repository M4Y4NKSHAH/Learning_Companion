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


class QuestionGeneratorEngine:
    """
    Hybrid Guiding Agent & Offline Question Generation Engine.
    Uses Gemini in a single-pass ultra-low-token 'Curriculum Architect' guiding mode
    to craft accurate theory, formulas, and flashcards with minimal token usage (~300 tokens total),
    backed by local Llama-3.2-3B and semantic NLP extraction.
    """

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

    def generate_guided_curriculum_blueprint(
        self,
        course_title: str,
        material_sample: str,
        subject: str = "General",
        tier: str = "Standard",
        detected_headings: Optional[List[str]] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        SINGLE-PASS GUIDING AGENT:
        Uses a single, highly-focused call to Gemini (spending <400 tokens total)
        to design the complete, authentic academic theory, exact governing formulas, 
        and high-retention flashcards for the entire course.
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
            "8. 'cards': Exactly 3 distinct, high-impact flashcards [{\"topic\": \"...\", \"question\": \"...\", \"answer\": \"• ...\\n• ...\"}].\n\n"
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

    def generate_chapter_theory_and_cards(
        self,
        chapter_title: str,
        chapter_text: str,
        subject: str = "General",
        tier: str = "Standard",
        chapter_index: int = 1
    ) -> Dict[str, Any]:
        """
        Synthesizes authentic chapter theory, learning objectives, and flashcards directly
        from the chapter's own text content.
        Hierarchy: 1. Gemini (if key available) -> 2. Local Llama-3.2-3B -> 3. Content-Grounded Semantic NLP.
        """
        sample_context = chapter_text[:3500]

        guardrails = get_grade_level_guardrails(tier)
        prohibitions = "\n".join(f"- {p}" for p in guardrails["strict_prohibitions"])
        requirements = "\n".join(f"- {r}" for r in guardrails["mandatory_requirements"])

        # 1. Gemini Single-Chapter Synthesis (accurate, chapter-isolated)
        gemini = self._get_gemini_guide_model()
        if gemini:
            try:
                prompt = (
                    f"You are an expert curriculum architect for {subject}.\n"
                    f"TARGET LEARNER LEVEL: {guardrails['label']} ({guardrails['audience']})\n"
                    f"Tone: {guardrails['tone']}\n"
                    f"Math/Conceptual Ceiling: {guardrails['math_ceiling']}\n"
                    f"STRICT PROHIBITIONS (DO NOT VIOLATE):\n{prohibitions}\n"
                    f"MANDATORY REQUIREMENTS:\n{requirements}\n\n"
                    f"Analyze this specific chapter:\n"
                    f"Chapter {chapter_index}: '{chapter_title}'\n"
                    f"Chapter Content:\n\"\"\"{sample_context[:2500]}\"\"\"\n\n"
                    "Produce a JSON object with:\n"
                    "1. 'summary': 2-3 sentence rigorous summary explaining the core physical/conceptual mechanisms.\n"
                    "2. 'objectives': Array of 3 distinct learning objectives.\n"
                    "3. 'cards': Exactly 3 flashcards [{\"topic\": \"Specific Concept/Law Name\", \"question\": \"Conceptual question?\", \"answer\": \"• Key point 1\\n• Key point 2\"}].\n"
                    "4. 'principles': [{\"title\": \"...\", \"content\": \"...\", \"tag\": \"Core Axiom\"}].\n"
                    "5. 'formulations': [{\"title\": \"...\", \"formula\": \"...\", \"derivation\": \"...\", \"variables\": \"...\"}].\n"
                    "6. 'mental_models': [{\"concept\": \"...\", \"analogy\": \"...\", \"takeaway\": \"...\"}].\n"
                    "7. 'misconceptions': [{\"trap\": \"...\", \"correction\": \"...\"}].\n\n"
                    "Return ONLY raw JSON with no markdown fences."
                )
                res = gemini.invoke([HumanMessage(content=prompt)])
                clean_json = res.content.replace("```json", "").replace("```", "").strip()
                try:
                    parsed = json.loads(clean_json)
                except Exception:
                    sanitized_json = re.sub(r'\\(?![/\\bfnrtu"U])', r'\\\\', clean_json)
                    parsed = json.loads(sanitized_json)
                if isinstance(parsed, dict) and "cards" in parsed and len(parsed["cards"]) > 0:
                    cards = []
                    for idx, c in enumerate(parsed.get("cards", [])):
                        cards.append({
                            "id": f"c{chapter_index}_{idx+1}_{uuid.uuid4().hex[:4]}",
                            "topic": c.get("topic", chapter_title),
                            "question": c.get("question", f"Core principle in {chapter_title}"),
                            "answer": filter_for_grade_level(c.get("answer", "• Theoretical relationship and mechanics."), tier)
                        })
                    return {
                        "summary": filter_for_grade_level(parsed.get("summary", f"Core concepts in {chapter_title}"), tier),
                        "objectives": parsed.get("objectives", [f"Master fundamentals of {chapter_title}"]),
                        "cards": cards[:3],
                        "deep_theory": {
                            "principles": parsed.get("principles", [{"title": "Primary Law", "content": parsed.get("summary", ""), "tag": "Core Axiom"}]),
                            "formulations": parsed.get("formulations", [{"title": "Governing Formulation", "formula": f"Equations governing {chapter_title}", "derivation": "Derived from foundational conservation laws.", "variables": "State properties and constants."}]),
                            "mental_models": parsed.get("mental_models", [{"concept": "Intuition", "analogy": f"Conceptual equilibrium representing {chapter_title}.", "takeaway": "Track system state invariants."}]),
                            "misconceptions": parsed.get("misconceptions", [{"trap": "Formula misapplication", "correction": "Verify operational assumptions first."}])
                        }
                    }
            except Exception as e:
                print(f"[QGE] Gemini chapter synthesis fallback: {e}")

        # 2. Local Llama-3.2-3B
        if self.local_llm.is_available():
            try:
                local_res = self.local_llm.summarize_chapter_and_generate_cards(chapter_title, sample_context, subject)
                if local_res and "cards" in local_res and len(local_res["cards"]) > 0:
                    cards = []
                    for idx, c in enumerate(local_res.get("cards", [])):
                        cards.append({
                            "id": f"c{chapter_index}_{idx+1}_{uuid.uuid4().hex[:4]}",
                            "topic": c.get("topic", chapter_title),
                            "question": c.get("question", f"Key principle in {chapter_title}"),
                            "answer": c.get("answer", "• Essential theoretical relationship and governing concept.")
                        })
                    return {
                        "summary": local_res.get("summary", f"Core concepts in {chapter_title}"),
                        "objectives": local_res.get("objectives", [f"Master fundamentals of {chapter_title}"]),
                        "cards": cards[:3],
                        "deep_theory": {
                            "principles": [{"title": "Core Law", "content": local_res.get("summary", ""), "tag": "Core Axiom"}],
                            "formulations": [{"title": "Mathematical Model", "formula": f"Equations governing {chapter_title}", "derivation": "Derived from foundational conservation laws.", "variables": "State properties and constants."}],
                            "mental_models": [{"concept": "Intuition", "analogy": f"Conceptual equilibrium representing {chapter_title}.", "takeaway": "Maintain boundary condition awareness."}],
                            "misconceptions": [{"trap": "Formula misapplication", "correction": "Verify operational assumptions first."}]
                        }
                    }
            except Exception as e:
                print(f"[QGE] Local LLM warning: {e}")

        # 3. Content-Grounded Semantic NLP Synthesizer
        facts = self._extract_facts_from_text(chapter_text)
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', chapter_text) if len(s.strip()) > 35]
        key_definitions = [s for s in sentences if any(k in s.lower() for k in ['is defined as', 'refers to', 'states that', 'principle', 'law of', 'equation', 'formula', 'theorem', 'fundamental'])]
        key_formulas = [s for s in sentences if any(k in s.lower() for k in ['equation', 'formula', '=', 'proportional', 'constant', 'integral', 'derivative', 'function', 'state variable', 'rate of'])]
        
        summary = " ".join(key_definitions[:2]) if key_definitions else (" ".join(sentences[:2]) if sentences else f"Core theoretical curriculum for {chapter_title}.")
        
        # Build flashcards grounded in extracted facts
        is_cs = any(k in subject.lower() for k in ["computer", "software", "data", "algorithm", "code"])
        is_math = "math" in subject.lower()

        cards: List[Dict[str, str]] = []
        for f_idx, fact in enumerate(facts[:3], 1):
            card_id = f"card_ch{chapter_index}_{f_idx}_{uuid.uuid4().hex[:4]}"
            if fact.get("type") == "equation":
                if is_cs:
                    ans = f"• Governing Formulation: {fact['full']}\n• Mechanics: Defines algorithmic recurrence, complexity bound, or system relation.\n• Application: Apply with invariant validation and runtime efficiency."
                elif is_math:
                    ans = f"• Governing Formulation: {fact['full']}\n• Mechanics: Relates mathematical variables under domain constraints.\n• Application: Apply with algebraic rigor and domain validity."
                else:
                    ans = f"• Governing Formulation: {fact['full']}\n• Mechanics: Connects system state parameters.\n• Application: Apply with strict dimensional and unit consistency."
                cards.append({
                    "id": card_id,
                    "topic": f"{fact['lhs']} Formulation",
                    "question": f"What is the mathematical formulation and conceptual meaning of {fact['lhs']} in {chapter_title}?",
                    "answer": ans
                })
            elif fact.get("type") == "definition":
                if is_cs:
                    ans = f"• Core Statement: {fact['text']}.\n• Role: Establishes a fundamental abstraction or architectural construct.\n• Boundary: Valid within designated runtime, type, and complexity models."
                elif is_math:
                    ans = f"• Core Statement: {fact['text']}.\n• Role: Establishes a formal mathematical theorem or axiomatic definition.\n• Boundary: Valid within defined algebraic structures and coordinate domains."
                else:
                    ans = f"• Core Statement: {fact['text']}.\n• Role: Establishes the foundational theoretical framework.\n• Boundary: Valid within specified physical assumptions."
                cards.append({
                    "id": card_id,
                    "topic": fact["concept"],
                    "question": f"What does {fact['concept']} state and how does it apply to {chapter_title}?",
                    "answer": ans
                })
            elif fact.get("type") == "value":
                cards.append({
                    "id": card_id,
                    "topic": f"{fact['concept']} Parameter",
                    "question": f"What is the standard value or role of {fact['concept']} in {chapter_title}?",
                    "answer": f"• Reference Value: {fact['value']}\n• Significance: Acts as a critical system parameter or threshold.\n• Usage: Calibrates empirical state calculations."
                })

        # Backfill if fewer than 3 facts were extracted
        c1 = key_definitions[0] if key_definitions else (sentences[0] if sentences else chapter_title)
        c2 = key_formulas[0] if key_formulas else (key_definitions[1] if len(key_definitions) > 1 else (sentences[1] if len(sentences) > 1 else "Core structural relations"))
        
        fallback_templates = [
            ("Core Theory", f"What is the primary governing principle of {chapter_title}?", f"• Principle: {c1[:240]}\n• Focus: Invariant principles and domain mechanics."),
            ("System Architecture", f"How do the governing relations operate in {chapter_title}?", f"• Formulation: {c2[:240]}\n• Mechanics: Connects operational variables and execution components."),
            ("Problem Solving", f"What is the key problem-solving strategy for {chapter_title}?", "• Strategy: Deconstruct problems into fundamental axioms and modular abstractions.\n• Verification: Test solutions against boundary conditions and edge cases.")
        ]
        
        while len(cards) < 3 and len(cards) < len(fallback_templates):
            t_idx = len(cards)
            t_topic, t_q, t_a = fallback_templates[t_idx]
            cards.append({
                "id": f"card_ch{chapter_index}_{t_idx+1}_{uuid.uuid4().hex[:4]}",
                "topic": f"{chapter_title} - {t_topic}",
                "question": t_q,
                "answer": t_a
            })

        c_formula = next((f["full"] for f in facts if f.get("type") == "equation"), c2)
        deep_theory = self._build_subject_deep_theory(subject, chapter_title, c1, c2, c_formula)

        return {
            "summary": summary,
            "objectives": [
                f"Master the core axioms and mechanics of {chapter_title}",
                f"Apply governing principles of {chapter_title} to problem solving",
                f"Diagnose critical boundary conditions and common misconceptions"
            ],
            "cards": cards[:3],
            "deep_theory": deep_theory
        }

    @staticmethod
    def _build_subject_deep_theory(subject: str, chapter_title: str, c1: str, c2: str, c_formula: str) -> Dict[str, Any]:
        """Builds subject-appropriate axioms, formulations, mental models, and traps."""
        sub_low = subject.lower()
        if any(k in sub_low for k in ["computer", "software", "data", "algorithm", "code"]):
            return {
                "principles": [
                    {"title": f"Core Computational Principle: {chapter_title}", "content": c1, "tag": "Core Axiom"},
                    {"title": "System Architecture & Execution", "content": c2, "tag": "Mechanics"}
                ],
                "formulations": [
                    {"title": "Algorithmic / Complexity Model", "formula": c_formula if any(sym in c_formula for sym in ["O(", "T(n)", "="]) else "T(n) = O(f(n))", "derivation": "Derived from formal runtime step counting and recurrence decomposition.", "variables": "n: input data size, T(n): asymptotic computational steps, f(n): bounding growth function."}
                ],
                "mental_models": [
                    {"concept": "Deterministic Pipeline Model", "analogy": f"Conceptualize {chapter_title} as a structured state machine transforming inputs into outputs under invariant constraints.", "takeaway": "Maintain data abstraction barriers and invariant correctness."}
                ],
                "misconceptions": [
                    {"trap": "Confusing worst-case asymptotic bounds with average runtime execution", "correction": "Distinguish between worst-case Big-O, expected average case, and constant-factor memory overhead."}
                ]
            }
        elif "math" in sub_low:
            return {
                "principles": [
                    {"title": "Foundational Theorem / Axiom", "content": c1, "tag": "Core Axiom"},
                    {"title": "Analytical Mechanics", "content": c2, "tag": "Mechanics"}
                ],
                "formulations": [
                    {"title": "Mathematical Formulation", "formula": c_formula, "derivation": "Established via rigorous deductive proof from primitive mathematical axioms.", "variables": "Domain parameters, independent variables, and transformation constraints."}
                ],
                "mental_models": [
                    {"concept": "Geometric & Algebraic Symmetry", "analogy": f"View {chapter_title} as an invariant mapping preserving structural mathematical properties.", "takeaway": "Verify domain constraints and convergence conditions."}
                ],
                "misconceptions": [
                    {"trap": "Applying identities outside their valid mathematical domain", "correction": "Check domain validity, continuity, and boundary conditions prior to simplification."}
                ]
            }
        elif "bio" in sub_low or "chem" in sub_low:
            return {
                "principles": [
                    {"title": "Governing Natural Mechanism", "content": c1, "tag": "Core Axiom"},
                    {"title": "System Dynamics", "content": c2, "tag": "Mechanics"}
                ],
                "formulations": [
                    {"title": "Governing Reaction / System Model", "formula": c_formula, "derivation": "Derived from empirical observation and biochemical equilibrium relations.", "variables": "Concentrations, rate constants, reaction quotients, and biological state variables."}
                ],
                "mental_models": [
                    {"concept": "Feedback & Dynamic Equilibrium", "analogy": f"Understand {chapter_title} as a self-regulating feedback network balancing catalytic and inhibitory states.", "takeaway": "Track energy gradients and homeostasis."}
                ],
                "misconceptions": [
                    {"trap": "Assuming static equilibrium rather than dynamic biological balance", "correction": "Remember that molecular and biological systems maintain homeostatic steady states through continuous energy flux."}
                ]
            }
        else:
            return {
                "principles": [
                    {"title": "Primary Governing Principle", "content": c1, "tag": "Core Axiom"},
                    {"title": "Analytical Mechanics", "content": c2, "tag": "Mechanics"}
                ],
                "formulations": [
                    {"title": "Governing Formulation", "formula": c_formula, "derivation": "Derived from foundational conservation and symmetry principles.", "variables": "State variables, proportionalities, and physical boundary constraints."}
                ],
                "mental_models": [
                    {"concept": "Equilibrium & Conservation Model", "analogy": f"Think of {chapter_title} as a dynamic system governed by conservation constraints.", "takeaway": "Track invariants, boundary limits, and energy conservation."}
                ],
                "misconceptions": [
                    {"trap": "Applying equations outside operational validity bounds", "correction": "Always establish operational domain, inertial frame, and physical assumptions prior to calculation."}
                ]
            }

    @staticmethod
    def _extract_facts_from_text(text: str) -> List[Dict[str, str]]:
        """Extracts concrete facts: named laws, equations, values, and definitions directly from text."""
        facts: List[Dict[str, str]] = []
        if not text:
            return facts

        # 1. Named definitions / Laws / Theories / Historical Concepts across ALL subjects:
        def_pattern = re.compile(
            r"([A-Z][a-zA-Z0-9\s'\-]{2,40}(?:Law|Theorem|Principle|Equation|Concept|Effect|Constant|Property|Doctrine|Treaty|Movement|Era|Theory|Policy|Philosophy|System|Model|Paradigm|Process|Algorithm)?)\s+(?:states\s+that|is\s+defined\s+as|refers\s+to|describes|is\s+the|was\s+the|was\s+a|represents|signifies)\s+([^.!?\n]{15,180})[.!?]",
            re.IGNORECASE
        )
        for m in def_pattern.finditer(text):
            concept = m.group(1).strip()
            desc = m.group(2).strip()
            if len(concept) > 2 and len(desc) > 15:
                facts.append({"type": "definition", "concept": concept, "text": desc})

        # 2. Mathematical/Physical Equations: e.g. "Delta U = Q - W", "PV = nRT", "F = m * a"
        eq_pattern = re.compile(
            r"([A-Za-zΔ][A-Za-z0-9_\s]{0,25})\s*=\s*([A-Za-z0-9_\+\-\*\/\(\)\.\s]{1,40})(?=[,\.;\n]|$)"
        )
        for m in eq_pattern.finditer(text):
            raw_lhs = m.group(1).strip()
            raw_rhs = m.group(2).strip()
            
            # Clean lhs: isolate the actual variable/symbol tokens
            lhs_tokens = raw_lhs.lstrip("({[").split()
            if not lhs_tokens:
                continue
            
            if len(lhs_tokens) >= 2 and lhs_tokens[-2].lower() in ["delta", "net", "avg", "total"]:
                lhs = f"{lhs_tokens[-2]} {lhs_tokens[-1]}"
            else:
                lhs = lhs_tokens[-1]
            
            # Strip non-symbol prefix words if any remained
            lhs = re.sub(r'^(?:is|are|the|an|that|where|equation|formula|of)\s+', '', lhs, flags=re.I).strip()
            
            # Clean rhs: strip trailing punctuation and parentheses
            rhs = raw_rhs.rstrip(")}].;, ").strip()
            if lhs and rhs and len(rhs) >= 1 and not any(kw in lhs.lower() for kw in ["http", "www", "chapter", "is"]):
                facts.append({"type": "equation", "lhs": lhs, "rhs": rhs, "full": f"{lhs} = {rhs}"})

        # 3. Specific Constants / Quantities: e.g. "8.314 J/(mol*K)", "0 m/s²", "9.8 m/s²"
        val_pattern = re.compile(
            r"([A-Za-z\s]{3,35})\s+(?:is|equals?|of|value)\s+([+-]?\d+(?:\.\d+)?\s*(?:m\/s²?|N|J|K|Hz|kg|Pa|mol|W|V|A|°C)?\b)",
            re.IGNORECASE
        )
        for m in val_pattern.finditer(text):
            concept = m.group(1).strip()
            val = m.group(2).strip()
            if len(concept) > 2 and len(val) > 0:
                facts.append({"type": "value", "concept": concept, "value": val})

        return facts[:12]

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
            else:
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
            
            # --- MCQ Quiz ---
            # Try to build a question around a real equation, value, or definition
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
            # Ensure unique options
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

            # --- Short-Answer Final Exam Item ---
            # Concrete expected answer allows the short-answer evaluator to reliably grade
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
