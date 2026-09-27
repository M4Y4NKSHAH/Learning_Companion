"""
Pedagogical Guardrails & Context Grounding Engine
Enforces:
1. Grade-Level Appropriate Content (prevents Class 12 complexity from leaking into Class 9).
2. Course Material as Ground Truth (strictly anchors explanations to initial ingested textbook).
3. Off-Topic Information Guardrails (detects irrelevant queries and gently steers learner back).
"""

import re
from typing import Tuple, List, Dict, Any, Optional


GRADE_TIER_CONFIG: Dict[str, Dict[str, Any]] = {
    "introductory": {
        "label": "Secondary / Class 9-10 (Introductory)",
        "audience": "Class 9-10 high school students (ages 14-16)",
        "tone": "Warm, encouraging, intuitive, visual, and grounded in real-world everyday analogies.",
        "math_ceiling": "Elementary algebra, basic linear equations, arithmetic ratios, and qualitative physical laws.",
        "strict_prohibitions": [
            "NO calculus (strictly NO derivatives dy/dx, NO integrals, NO partial derivatives).",
            "NO tensor notation, multi-variable vector fields, or college-level jargon.",
            "NO advanced university-level biochemistry pathways or thermodynamic potentials.",
            "Never overwhelm the student with university-level formalisms."
        ],
        "mandatory_requirements": [
            "Always anchor the explanation in an intuitive everyday analogy (e.g. water pipes, sports, cars, playground swings).",
            "Explain step-by-step with simple arithmetic where numbers are needed.",
            "Prioritize qualitative understanding of 'why' before formulas."
        ]
    },
    "standard": {
        "label": "Senior Secondary / Class 11-12 (Standard)",
        "audience": "Class 11-12 high school & college-prep students (ages 16-18)",
        "tone": "Analytical, rigorous, concept-grounded, and mathematically structured.",
        "math_ceiling": "Vector mechanics, single-variable differential and integral calculus, system state equations.",
        "strict_prohibitions": [
            "Do not skip derivation steps or assume unstated boundary conditions.",
            "Avoid overly abstract graduate-level topology or advanced quantum field theory."
        ],
        "mandatory_requirements": [
            "Explicitly define physical and mathematical variables with units.",
            "Walk through governing formulations step-by-step.",
            "Highlight core physical principles before substituting numerical values."
        ]
    },
    "advanced": {
        "label": "Undergraduate / Advanced Academic",
        "audience": "University undergraduates and advanced researchers",
        "tone": "Scholarly, precise, mathematically exhaustive, and first-principles driven.",
        "math_ceiling": "Multivariate calculus, differential equations, linear algebra, tensor formulations.",
        "strict_prohibitions": [
            "Do not oversimplify or hand-wave critical edge cases.",
            "Ensure rigorous boundary conditions are explicitly stated."
        ],
        "mandatory_requirements": [
            "Provide formal derivations, state invariant conservation laws, and address empirical edge cases."
        ]
    }
}


def normalize_academic_tier(tier_or_grade: Optional[str]) -> str:
    """Normalizes any grade or tier string ('Class 9', 'Grade 10', 'Advanced', 'Senior Secondary') into canonical tier key."""
    if not tier_or_grade:
        return "standard"

    s = tier_or_grade.lower().strip()
    if any(k in s for k in ["college", "university", "advanced", "master", "phd", "graduate", "undergrad"]):
        return "advanced"
    elif any(k in s for k in ["senior", "11", "12", "standard", "higher secondary"]):
        return "standard"
    elif any(k in s for k in ["9", "10", "intro", "secondary", "middle", "beginner", "basic", "junior"]):
        return "introductory"
    else:
        return "standard"


def get_grade_level_guardrails(tier_or_grade: Optional[str]) -> Dict[str, Any]:
    """Returns the pedagogical configuration for the learner's specific academic level."""
    tier_key = normalize_academic_tier(tier_or_grade)
    return GRADE_TIER_CONFIG.get(tier_key, GRADE_TIER_CONFIG["standard"])


# Off-topic patterns (entertainment, gaming, politics, unrelated chit-chat, malware, crypto, recipes, movies)
OFF_TOPIC_PATTERNS = [
    re.compile(r"\b(fortnite|minecraft|roblox|gta|playstation|xbox|nintendo|pokemon|anime|manga|valorant|cod|pubg|fifa|video\s+games?)\b", re.IGNORECASE),
    re.compile(r"\b(write a poem about love|tell me a joke about dogs|sing a song|who won the super bowl|who is the best celebrity|taylor swift|kanye|drake|messi|ronaldo)\b", re.IGNORECASE),
    re.compile(r"\b(who should i vote for|democrat or republican|election results|write malware|hack into|ddos|bypass password|crypto|bitcoin|buy doge|casino|betting tips)\b", re.IGNORECASE),
    re.compile(r"\b(recipe|cook dinner|bake a cake|movies?|netflix|disney\+|hulu|cinema|hollywood|bollywood|tv\s+shows?)\b", re.IGNORECASE),
]


def check_information_guardrails(
    student_query: str,
    course_title: str = "Course",
    chapter_title: str = "Active Chapter",
    subject: str = "Subject",
    retrieved_context: Optional[List[str]] = None
) -> Tuple[bool, Optional[str]]:
    """
    Evaluates whether the student's question is relevant to the course curriculum
    or violates off-topic guardrails.
    Returns: (is_valid, deflection_message_if_invalid)
    """
    clean_q = student_query.strip()
    if len(clean_q) < 2:
        return True, None

    # Check for explicit off-topic entertainment / malicious prompts
    for pattern in OFF_TOPIC_PATTERNS:
        if pattern.search(clean_q):
            deflection = (
                f"**🎯 Course Guardrail Notice**:\n\n"
                f"That inquiry falls outside our curriculum scope for **{course_title}** ({chapter_title}).\n\n"
                f"As your academic companion, I am dedicated to helping you master **{subject}**. "
                f"Let's redirect our focus back to the core principles of **{chapter_title}**. "
                f"What part of this chapter would you like to review or explore?"
            )
            return False, deflection

    return True, None


# Calculus / advanced symbols strictly prohibited for Introductory (Class 9-10)
CLASS_9_PROHIBITED_PATTERNS = [
    re.compile(r"\b(d[yxz]/d[txz]|dy/dx|dv/dt|dx/dt|integral|derivative|differentiation|integration)\b", re.IGNORECASE),
    re.compile(r"(\\int|\\frac\{d|\\partial|\\nabla|\\oint|\\lim_)", re.IGNORECASE),
    re.compile(r"\b(hamiltonian|lagrangian|maxwell'?s\s+equations|schrodinger|wavefunction)\b", re.IGNORECASE),
]


def filter_for_grade_level(response_text: str, tier_or_grade: str) -> str:
    """
    Post-generation safety rail:
    If learner is Class 9-10 (Introductory), ensures calculus notation or university-level
    formalisms do not leak into the response. Replaces with intuitive algebra.
    """
    tier_key = normalize_academic_tier(tier_or_grade)
    if tier_key != "introductory":
        return response_text

    cleaned = response_text
    # Sanitize calculus terms if an LLM hallucinated them for a Class 9 student
    for pattern in CLASS_9_PROHIBITED_PATTERNS:
        if pattern.search(cleaned):
            # Replace calculus differentials with elementary rate of change or simple deltas
            cleaned = re.sub(r"\b(dv/dt|d[vV]/d[tT])\b", "rate of change of speed (change in speed / time)", cleaned)
            cleaned = re.sub(r"\b(dx/dt|ds/dt)\b", "speed (distance / time)", cleaned)
            cleaned = re.sub(r"\b(dy/dx)\b", "ratio of change", cleaned)
            cleaned = re.sub(r"(\\int|\\oint)", "sum of values", cleaned)
            cleaned = re.sub(r"(\\partial|\\nabla)", "change", cleaned)

    return cleaned


def construct_grounded_system_prompt(
    role: str,
    subject: str,
    tier_or_grade: str,
    chapter_title: str,
    course_title: str,
    retrieved_textbook_chunks: List[str],
    current_question_context: Optional[str] = None,
    mode_directive: Optional[str] = None
) -> str:
    """
    Constructs a strictly grounded, level-appropriate system prompt where the initial
    course material serves as the authoritative source file.
    """
    guardrails = get_grade_level_guardrails(tier_or_grade)
    prohibitions_str = "\n".join(f"- {p}" for p in guardrails["strict_prohibitions"])
    requirements_str = "\n".join(f"- {r}" for r in guardrails["mandatory_requirements"])
    
    context_str = "\n---\n".join(retrieved_textbook_chunks) if retrieved_textbook_chunks else "No specific textbook excerpt retrieved."

    prompt = (
        f"You are the authoritative {role} for {subject}.\n"
        f"COURSE: '{course_title}' | CHAPTER: '{chapter_title}'\n"
        f"TARGET LEARNER LEVEL: {guardrails['label']} ({guardrails['audience']})\n\n"
        f"══════════════════════════════════════════════════════════════════════════════\n"
        f"PRIMARY GROUND TRUTH: INGESTED COURSE MATERIAL (TEXTBOOK)\n"
        f"══════════════════════════════════════════════════════════════════════════════\n"
        f"The following excerpts are extracted directly from the student's authoritative course text:\n"
        f"{context_str}\n\n"
        f"══════════════════════════════════════════════════════════════════════════════\n"
        f"PEDAGOGICAL & LEVEL-APPROPRIATE GUARDRAILS\n"
        f"══════════════════════════════════════════════════════════════════════════════\n"
        f"Tone: {guardrails['tone']}\n"
        f"Mathematical / Conceptual Ceiling: {guardrails['math_ceiling']}\n\n"
        f"STRICT PROHIBITIONS (DO NOT VIOLATE):\n"
        f"{prohibitions_str}\n\n"
        f"MANDATORY TEACHING PRACTICES:\n"
        f"{requirements_str}\n\n"
        f"INFORMATION GROUNDING RULES:\n"
        f"1. Base your explanations, proofs, and definitions strictly on the verified course material above.\n"
        f"2. Never hallucinate facts or introduce ungrounded theories outside this subject level.\n"
        f"3. Use plain text and readable ASCII math (e.g. F = m * a, v = u + a*t). Do NOT use complex LaTeX tags like \\frac or $$.\n"
    )

    if current_question_context:
        prompt += f"\nACTIVE QUESTION IN CONTEXT: {current_question_context}\n"

    if mode_directive:
        prompt += f"\nROLE SPECIFIC DIRECTIVES:\n{mode_directive}\n"

    return prompt
