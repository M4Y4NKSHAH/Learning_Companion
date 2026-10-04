import os
import operator
from typing import Annotated, TypedDict, Literal, Optional, List, Dict, Any
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END

from fuzzy_engine import FuzzyMarkingSystem
from hint_utils import sanitize_hint_text
from local_llm_service import LocalLLMService
from course_manager import CourseManager
from pedagogical_guardrails import (
    check_information_guardrails,
    construct_grounded_system_prompt,
    filter_for_grade_level,
    normalize_academic_tier,
)


class AgentState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], operator.add]
    time_taken_seconds: int
    consecutive_errors: int
    requires_remedial_routing: bool
    depth_level: str  # "surface", "deep", "solution", "hint", "guardrail_deflection"
    fuzzy_score: float
    performance_tier: str
    linguistic_remark: str
    degree_of_failure: float
    retrieved_curriculum: list[str]
    active_agent_node: str
    subject: str
    academic_tier: str
    course_id: str
    chapter_id: str
    course_title: str
    chapter_title: str
    guardrail_deflection: Optional[str]
    current_question: dict
    inquiry_type: str  # "hint", "solution", "discussion"


def get_gemini_api_key() -> str:
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""


def retrieve_context_node(state: AgentState):
    latest_query = state["messages"][-1].content if state.get("messages") else "core concepts"
    course_id = state.get("course_id")
    chapter_id = state.get("chapter_id")
    subject = state.get("subject", "Physics")
    tier = state.get("academic_tier", "Class 10")

    course_title = state.get("course_title") or f"{subject} ({tier})"
    chapter_title = state.get("chapter_title") or "Active Topic"

    if course_id:
        try:
            course_obj = CourseManager.get_course_by_id(course_id)
            if course_obj:
                course_title = course_obj.get("title", course_title)
                for ch in course_obj.get("chapters", []):
                    if ch.get("chapter_id") == chapter_id or str(ch.get("chapter_index")) == str(chapter_id):
                        chapter_title = ch.get("title", chapter_title)
                        break
        except Exception as ce:
            print(f"[tutor_graph] Course resolution warning: {ce}")

    try:
        from database_ingest import get_db_pipeline
        pipeline = get_db_pipeline()

        if course_id and chapter_id:
            # Custom course with chapter-level isolation: zero cross-chapter leakage via hybrid retrieval
            context = pipeline.query_hybrid(
                query=latest_query,
                course_id=course_id,
                chapter_id=chapter_id,
                n_results=4
            )
        elif course_id:
            # Custom course without explicit chapter specification: hybrid retrieval
            context = pipeline.query_hybrid(
                query=latest_query,
                course_id=course_id,
                n_results=4
            )
        else:
            # Built-in curriculum
            results = pipeline.curriculum_collection.query(
                query_texts=[latest_query],
                n_results=3,
                where={"$and": [
                    {"academic_tier": tier},
                    {"subject": subject}
                ]}
            )
            context = results['documents'][0] if results and results.get('documents') else []
    except Exception as e:
        print(f"[tutor_graph] Context retrieval fallback: {e}")
        context = [f"Core textbook reference material for {tier} level structural {subject} parameters."]

    return {
        "retrieved_curriculum": context,
        "course_title": course_title,
        "chapter_title": chapter_title,
        "active_agent_node": "Context Retriever Node"
    }


def analyze_depth_and_mamdani_node(state: AgentState):
    raw_msg = state["messages"][-1].content if state.get("messages") else ""
    # Extract only the student inquiry if message contains question metadata prefix
    if " | Student Inquiry: " in raw_msg:
        student_inquiry = raw_msg.split(" | Student Inquiry: ")[-1].strip()
    else:
        student_inquiry = raw_msg.strip()

    subject = state.get("subject", "Science")
    course_title = state.get("course_title", f"{subject} Course")
    chapter_title = state.get("chapter_title", "Active Chapter")

    # ══════════════════════════════════════════════════════════════════════════════
    # GUARDRAIL STAGE: OFF-TOPIC INFORMATION DETECTION
    # ══════════════════════════════════════════════════════════════════════════════
    is_valid, deflection = check_information_guardrails(
        student_query=student_inquiry,
        course_title=course_title,
        chapter_title=chapter_title,
        subject=subject,
        retrieved_context=state.get("retrieved_curriculum", [])
    )
    if not is_valid:
        return {
            "requires_remedial_routing": False,
            "depth_level": "guardrail_deflection",
            "fuzzy_score": 50.0,
            "performance_tier": "Developing",
            "linguistic_remark": "Off-topic inquiry deflected by course guardrails",
            "degree_of_failure": 0.0,
            "active_agent_node": "Course Guardrail Deflector",
            "guardrail_deflection": deflection
        }

    inquiry_lower = student_inquiry.lower()
    inquiry_type = (state.get("inquiry_type") or "discussion").lower()
    errors = state.get("consecutive_errors", 0)
    latency = state.get("time_taken_seconds", 15)

    # Specific keyword lists for user inquiries
    hint_keywords = [
        "hint", "clue", "nudge", "guide me", "give me a hint", "need a hint",
        "help me think", "stuck", "direction", "how do i start", "request a hint"
    ]
    solution_keywords = [
        "give me the answer", "give answer", "tell me the answer", "what is the answer",
        "show full solution", "unlock full solution", "reveal solution", "full solution",
        "give solution", "need solution", "show solution", "just tell me the answer",
        "what is the solution", "give whole answer", "unlock solution", "tell the answer",
        "give me answer", "show answer"
    ]

    has_explicit_solution = inquiry_type == "solution" or any(k in inquiry_lower for k in solution_keywords)
    has_explicit_hint = inquiry_type == "hint" or any(k in inquiry_lower for k in hint_keywords)
    has_failed_multiple = errors >= 2

    # Calibrate Mamdani Fuzzy System inputs based on inquiry intent
    if has_explicit_solution:
        base_accuracy = 20.0
        error_severity = 0.85
    elif has_explicit_hint:
        base_accuracy = 55.0
        error_severity = 0.35
    elif has_failed_multiple:
        base_accuracy = 30.0
        error_severity = 0.70
    else:
        word_count = len(inquiry_lower.split())
        deep_keywords = ["why", "how", "formula", "derive", "explain", "proof", "mechanism", "vector", "step by step"]
        if word_count >= 8 or any(k in inquiry_lower for k in deep_keywords):
            base_accuracy = 90.0
            error_severity = 0.1
        else:
            base_accuracy = 70.0
            error_severity = 0.35

    attempts_count = max(1, errors + 1)
    hints_count = 1 if has_explicit_hint else 0

    # Run Mamdani Fuzzy Inference Engine for internal metrics
    eval_result = FuzzyMarkingSystem.evaluate_performance(
        accuracy_pct=base_accuracy,
        latency_seconds=latency,
        attempts_count=attempts_count,
        error_severity=error_severity,
        hints_requested=hints_count
    )
    fuzzy_score = eval_result["fuzzy_score"]
    performance_tier = eval_result["performance_tier"]
    linguistic_remark = eval_result["linguistic_remark"]
    degree_of_failure = eval_result["degree_of_failure"]

    # Determine node routing:
    # 1. Explicit hint -> Socratic Hint Node (NEVER reveals answer)
    # 2. Explicit solution request -> Direct Explainer Node
    # 3. Deep inquiry -> Deep Inquiry Discussion Node
    # 4. Surface inquiry -> Surface Discussion Node
    if has_explicit_hint and not has_explicit_solution:
        depth = "hint"
        node_name = "Socratic Hint Node"
        requires_remedial = False
    elif has_explicit_solution:
        depth = "solution"
        node_name = "Direct Explainer Node"
        requires_remedial = True
    elif base_accuracy >= 85.0 or performance_tier in ["High Mastery", "Moderate Mastery"]:
        depth = "deep"
        node_name = "Deep Inquiry Discussion Node"
        requires_remedial = False
    else:
        depth = "surface"
        node_name = "Surface Discussion Node"
        requires_remedial = False

    return {
        "requires_remedial_routing": requires_remedial,
        "depth_level": depth,
        "fuzzy_score": fuzzy_score,
        "performance_tier": performance_tier,
        "linguistic_remark": linguistic_remark,
        "degree_of_failure": degree_of_failure,
        "active_agent_node": node_name
    }


def guardrail_deflection_node(state: AgentState):
    """Handles deflected off-topic queries gracefully with academic redirection."""
    deflection_msg = state.get("guardrail_deflection") or (
        f"Let's redirect our focus back to the core principles of {state.get('subject', 'the course')}."
    )
    return {
        "messages": [AIMessage(content=deflection_msg)],
        "active_agent_node": "Course Guardrail Deflector"
    }


def _execute_tutor_generation(
    student_query: str,
    system_prompt: str,
    fallback_text: str,
    expected_answer: Optional[str] = None,
    tier: str = "Class 10",
    temperature: float = 0.3
) -> str:
    """
    Tier-Enforced Generation Dispatcher:
    1. Local LLM Service (Ollama / Llama-3.2-3B) with zero token costs and offline execution.
    2. Gemini Flash API if available.
    3. Dynamic Rule-based Curated Fallback.
    All responses pass through filter_for_grade_level to prevent Class 12 calculus leaking into Class 9.
    """
    # 1. Try Local Ollama LLM Service (Offline, 0 tokens)
    try:
        local_service = LocalLLMService()
        if local_service.is_available():
            resp = local_service.generate(
                prompt=student_query,
                system_prompt=system_prompt,
                temperature=temperature
            )
            if resp and len(resp.strip()) > 10:
                cleaned = filter_for_grade_level(resp.strip(), tier)
                if expected_answer:
                    cleaned = sanitize_hint_text(cleaned, expected_answer)
                return cleaned
    except Exception as le:
        print(f"[tutor_graph] Local LLM warning: {le}")

    # 2. Try Gemini Cloud Fallback
    api_key = get_gemini_api_key()
    if api_key:
        try:
            try:
                from backend.question_generator import normalize_ai_content
            except ImportError:
                from question_generator import normalize_ai_content
            model_name = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
            try:
                model = ChatGoogleGenerativeAI(model=model_name, temperature=temperature, google_api_key=api_key)
            except Exception:
                model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=temperature, google_api_key=api_key)
            payload = [HumanMessage(content=system_prompt), HumanMessage(content=student_query)]
            response = model.invoke(payload)
            if response and response.content:
                raw_str = normalize_ai_content(response.content).strip()
                cleaned = filter_for_grade_level(raw_str, tier)
                if expected_answer:
                    cleaned = sanitize_hint_text(cleaned, expected_answer)
                return cleaned
        except Exception as ge:
            print(f"[tutor_graph] Gemini API warning: {ge}")

    # 3. Curated Rule-based Fallback
    cleaned_fallback = filter_for_grade_level(fallback_text, tier)
    if expected_answer:
        cleaned_fallback = sanitize_hint_text(cleaned_fallback, expected_answer)
    return cleaned_fallback


def socratic_hint_node(state: AgentState):
    current_q = state.get("current_question") or {}
    subject = state.get("subject", "Physics")
    tier = state.get("academic_tier", "Class 10")
    concept = current_q.get("concept", "Core Concept")
    expected = current_q.get("expected_answer", "")
    curated_hint = current_q.get("hint")
    course_title = state.get("course_title", f"{subject} ({tier})")
    chapter_title = state.get("chapter_title", "Active Chapter")
    retrieved_chunks = state.get("retrieved_curriculum", [])

    user_query = state["messages"][-1].content if state.get("messages") else "Give me a hint"

    mode_directive = (
        "CRITICAL HINT INSTRUCTIONS:\n"
        "1. Provide a pedagogical hint or conceptual clue to guide the student towards solving the question.\n"
        "2. STRICT PROHIBITION: NEVER reveal the final numerical value, exact answer, or completed calculation.\n"
        "3. End with a guiding question to prompt the student's next step."
    )

    system_prompt = construct_grounded_system_prompt(
        role="Socratic Academic Tutor and Hint Guide",
        subject=subject,
        tier_or_grade=tier,
        chapter_title=chapter_title,
        course_title=course_title,
        retrieved_textbook_chunks=retrieved_chunks,
        current_question_context=current_q.get("text", ""),
        mode_directive=mode_directive
    )

    if curated_hint:
        fallback = (
            f"**💡 Socratic Hint ({concept})**:\n\n"
            f"{curated_hint}\n\n"
            "• **Guiding Step**: How can you apply this principle to find the result?"
        )
    else:
        fallback = (
            f"**💡 Socratic Hint ({concept})**:\n\n"
            f"In {subject}, think carefully about how the key parameters in this problem relate to **{concept}**.\n\n"
            "• **Guiding Step**: What known values are given, and what formula or relationship connects them?"
        )

    content = _execute_tutor_generation(
        student_query=user_query,
        system_prompt=system_prompt,
        fallback_text=fallback,
        expected_answer=expected,
        tier=tier,
        temperature=0.3
    )

    return {"messages": [AIMessage(content=content)], "active_agent_node": "Socratic Hint Node"}


def surface_discussion_node(state: AgentState):
    current_q = state.get("current_question") or {}
    subject = state.get("subject", "Physics")
    tier = state.get("academic_tier", "Class 10")
    concept = current_q.get("concept") or subject
    course_title = state.get("course_title", f"{subject} ({tier})")
    chapter_title = state.get("chapter_title", "Active Chapter")
    retrieved_chunks = state.get("retrieved_curriculum", [])

    user_query = state["messages"][-1].content if state.get("messages") else "Explain this concept"

    mode_directive = (
        "INSTRUCTION:\n"
        "The student shared a surface query or introductory question.\n"
        "1. Acknowledge their specific inquiry directly.\n"
        "2. Provide a clear, intuitive explanation using a relatable real-world analogy.\n"
        "3. End with a leading question to help them explore further."
    )

    system_prompt = construct_grounded_system_prompt(
        role="Engaging AI Discussion Tutor",
        subject=subject,
        tier_or_grade=tier,
        chapter_title=chapter_title,
        course_title=course_title,
        retrieved_textbook_chunks=retrieved_chunks,
        current_question_context=current_q.get("text", ""),
        mode_directive=mode_directive
    )

    fallback = (
        f"Regarding your query on **{concept}** in {subject}:\n\n"
        f"In {subject} ({tier}), this concept explores the core principles of {concept}. "
        "What specific variable or idea would you like to analyze step by step?"
    )

    content = _execute_tutor_generation(
        student_query=user_query,
        system_prompt=system_prompt,
        fallback_text=fallback,
        tier=tier,
        temperature=0.3
    )

    return {"messages": [AIMessage(content=content)], "active_agent_node": "Surface Discussion Node"}


def deep_discussion_node(state: AgentState):
    current_q = state.get("current_question") or {}
    subject = state.get("subject", "Physics")
    tier = state.get("academic_tier", "Class 10")
    concept = current_q.get("concept") or subject
    course_title = state.get("course_title", f"{subject} ({tier})")
    chapter_title = state.get("chapter_title", "Active Chapter")
    retrieved_chunks = state.get("retrieved_curriculum", [])

    user_query = state["messages"][-1].content if state.get("messages") else "Detailed derivation"

    mode_directive = (
        "INSTRUCTION:\n"
        "The student submitted an in-depth analytical query.\n"
        "1. Provide a comprehensive breakdown matching their intellectual depth.\n"
        "2. Explicitly include relevant equations, mechanisms, or derivations appropriate to their grade level.\n"
        "3. Conclude with a challenging follow-up question or advanced edge-case scenario."
    )

    system_prompt = construct_grounded_system_prompt(
        role="Expert Academic Discussion Mentor",
        subject=subject,
        tier_or_grade=tier,
        chapter_title=chapter_title,
        course_title=course_title,
        retrieved_textbook_chunks=retrieved_chunks,
        current_question_context=current_q.get("text", ""),
        mode_directive=mode_directive
    )

    fallback = (
        f"Analyzing your inquiry regarding **{concept}** in {subject}:\n\n"
        f"• **Governing Principle**: At the {tier} level, {concept} provides the structural foundation for understanding system dynamics in {subject}.\n"
        f"• **Application**: Consider how the given parameters interact under these governing rules.\n\n"
        "Would you like to explore an edge case or work through a detailed derivation?"
    )

    content = _execute_tutor_generation(
        student_query=user_query,
        system_prompt=system_prompt,
        fallback_text=fallback,
        tier=tier,
        temperature=0.2
    )

    return {"messages": [AIMessage(content=content)], "active_agent_node": "Deep Inquiry Discussion Node"}


def direct_explanation_node(state: AgentState):
    current_q = state.get("current_question") or {}
    subject = state.get("subject", "Physics")
    tier = state.get("academic_tier", "Class 10")
    concept = current_q.get("concept", "Core Concept")
    curated_sol = current_q.get("solution")
    course_title = state.get("course_title", f"{subject} ({tier})")
    chapter_title = state.get("chapter_title", "Active Chapter")
    retrieved_chunks = state.get("retrieved_curriculum", [])

    user_query = state["messages"][-1].content if state.get("messages") else "Show the full solution"

    mode_directive = (
        "CRITICAL INSTRUCTION:\n"
        "1. State the EXPLICIT DIRECT ANSWER in bold on line 1 (e.g. **Direct Answer: [result]**).\n"
        "2. Show the step-by-step formula and calculation walkthrough.\n"
        "3. Give the concrete answer specifically to the question asked."
    )

    system_prompt = construct_grounded_system_prompt(
        role="Direct Explainer and Master Solution Guide",
        subject=subject,
        tier_or_grade=tier,
        chapter_title=chapter_title,
        course_title=course_title,
        retrieved_textbook_chunks=retrieved_chunks,
        current_question_context=current_q.get("text", ""),
        mode_directive=mode_directive
    )

    if curated_sol:
        fallback = (
            f"**⚡ Full Solution & Direct Answer ({concept})**:\n\n"
            f"{curated_sol}"
        )
    else:
        fallback = (
            f"**⚡ Full Solution & Direct Answer ({concept})**:\n\n"
            f"• **Subject**: {subject} ({tier})\n"
            f"• **Key Concept**: {concept}\n"
            f"• **Approach**: Review the governing rules for {concept} to resolve this problem."
        )

    content = _execute_tutor_generation(
        student_query=user_query,
        system_prompt=system_prompt,
        fallback_text=fallback,
        tier=tier,
        temperature=0.1
    )

    return {"messages": [AIMessage(content=content)], "active_agent_node": "Direct Explainer Node"}


def route_after_analysis(state: AgentState) -> Literal["surface_discussion", "deep_discussion", "direct_explanation", "socratic_hint", "guardrail_deflection"]:
    depth = state.get("depth_level", "surface")
    if depth == "guardrail_deflection":
        return "guardrail_deflection"
    elif depth in ["solution", "remedial"]:
        return "direct_explanation"
    elif depth == "hint":
        return "socratic_hint"
    elif depth == "deep":
        return "deep_discussion"
    return "surface_discussion"


# Assembly of the Stateful Discussion Architecture Network
workflow = StateGraph(AgentState)
workflow.add_node("retrieve_context", retrieve_context_node)
workflow.add_node("analyze_depth", analyze_depth_and_mamdani_node)
workflow.add_node("guardrail_deflection", guardrail_deflection_node)
workflow.add_node("surface_discussion", surface_discussion_node)
workflow.add_node("deep_discussion", deep_discussion_node)
workflow.add_node("direct_explanation", direct_explanation_node)
workflow.add_node("socratic_hint", socratic_hint_node)

workflow.add_edge(START, "retrieve_context")
workflow.add_edge("retrieve_context", "analyze_depth")
workflow.add_conditional_edges(
    "analyze_depth",
    route_after_analysis,
    {
        "guardrail_deflection": "guardrail_deflection",
        "surface_discussion": "surface_discussion",
        "deep_discussion": "deep_discussion",
        "direct_explanation": "direct_explanation",
        "socratic_hint": "socratic_hint"
    }
)
workflow.add_edge("guardrail_deflection", END)
workflow.add_edge("surface_discussion", END)
workflow.add_edge("deep_discussion", END)
workflow.add_edge("direct_explanation", END)
workflow.add_edge("socratic_hint", END)

compiled_tutor_app = workflow.compile()