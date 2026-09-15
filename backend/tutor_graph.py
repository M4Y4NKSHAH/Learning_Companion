import os
import operator
from typing import Annotated, TypedDict, Literal
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, START, END
from fuzzy_engine import FuzzyMarkingSystem
from hint_utils import sanitize_hint_text


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]
    time_taken_seconds: int
    consecutive_errors: int
    requires_remedial_routing: bool
    depth_level: str  # "surface", "deep", "solution", "hint"
    fuzzy_score: float
    performance_tier: str
    linguistic_remark: str
    degree_of_failure: float
    retrieved_curriculum: list[str]
    active_agent_node: str
    subject: str
    academic_tier: str
    current_question: dict
    inquiry_type: str  # "hint", "solution", "discussion"



def get_gemini_api_key() -> str:
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""


def retrieve_context_node(state: AgentState):
    latest_query = state["messages"][-1].content if state.get("messages") else "core concepts"
    try:
        from database_ingest import DatabaseIngestPipeline
        pipeline = DatabaseIngestPipeline()
        results = pipeline.curriculum_collection.query(
            query_texts=[latest_query],
            n_results=3,
            where={"$and": [
                {"academic_tier": state.get("academic_tier", "Class 10")},
                {"subject": state.get("subject", "Physics")}
            ]}
        )
        context = results['documents'][0] if results and results.get('documents') else []
    except Exception:
        context = [f"Core textbook reference material for {state.get('academic_tier')} level structural {state.get('subject')} parameters."]
    return {"retrieved_curriculum": context, "active_agent_node": "Context Retriever Node"}


def analyze_depth_and_mamdani_node(state: AgentState):
    raw_msg = state["messages"][-1].content if state.get("messages") else ""
    # Extract only the student inquiry if message contains question metadata prefix
    if " | Student Inquiry: " in raw_msg:
        student_inquiry = raw_msg.split(" | Student Inquiry: ")[-1].strip().lower()
    else:
        student_inquiry = raw_msg.strip().lower()

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

    has_explicit_solution = inquiry_type == "solution" or any(k in student_inquiry for k in solution_keywords)
    has_explicit_hint = inquiry_type == "hint" or any(k in student_inquiry for k in hint_keywords)
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
        word_count = len(student_inquiry.split())
        deep_keywords = ["why", "how", "formula", "derive", "explain", "proof", "mechanism", "vector", "step by step"]
        if word_count >= 8 or any(k in student_inquiry for k in deep_keywords):
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



def socratic_hint_node(state: AgentState):
    api_key = get_gemini_api_key()
    context_str = "\n".join(state.get("retrieved_curriculum", []))
    current_q = state.get("current_question") or {}
    subject = state.get("subject", "Physics")
    concept = current_q.get("concept", "Core Concept")
    expected = current_q.get("expected_answer", "")
    curated_hint = current_q.get("hint")

    if api_key:
        try:
            model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.3, google_api_key=api_key)
            system_prompt = (
                f"You are a Socratic Academic Tutor for {subject} ({state.get('academic_tier', 'Class 10')}).\n"
                f"CURRENT QUESTION: {current_q.get('text', '')}\n"
                f"TARGET CONCEPT: {concept}\n"
                f"VERIFIED CURRICULUM CONTEXT:\n{context_str}\n\n"
                "CRITICAL HINT INSTRUCTIONS:\n"
                "1. Provide a pedagogical hint or conceptual clue to guide the student towards solving the question.\n"
                "2. STRICT PROHIBITION: NEVER reveal the final numerical value, exact answer, or completed calculation.\n"
                "3. End with a guiding question to prompt the student's next step.\n"
                "4. Use plain text and ASCII math only (NO LaTeX math tags like \\frac, \\times, $$)."
            )
            payload = [HumanMessage(content=system_prompt)] + state["messages"]
            response = model.invoke(payload)
            clean_content = sanitize_hint_text(response.content, expected)
            return {"messages": [AIMessage(content=clean_content)], "active_agent_node": "Socratic Hint Node"}
        except Exception as e:
            print(f"Gemini API error in socratic_hint_node: {e}")

    # Subject- and question-aware fallback hint
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
    return {"messages": [AIMessage(content=fallback)], "active_agent_node": "Socratic Hint Node"}


def surface_discussion_node(state: AgentState):
    api_key = get_gemini_api_key()
    context_str = "\n".join(state.get("retrieved_curriculum", []))
    current_q = state.get("current_question") or {}
    concept = current_q.get("concept") or state.get("subject", "Science")
    user_msg = state["messages"][-1].content if state.get("messages") else ""

    if api_key:
        try:
            model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.3, google_api_key=api_key)
            system_prompt = (
                f"You are an engaging AI Discussion Tutor for {state.get('subject', 'Physics')} ({state.get('academic_tier', 'Class 10')}).\n"
                f"CURRENT QUESTION CONTEXT: {current_q.get('text', '')}\n"
                f"CONCEPT: {concept}\n"
                f"VERIFIED TEXTBOOK CURRICULUM CONTEXT:\n{context_str}\n\n"
                "INSTRUCTION:\n"
                "The student shared a surface query or question.\n"
                "1. Acknowledge their specific inquiry.\n"
                "2. Provide a clear, intuitive explanation with a real-world analogy.\n"
                "3. End with a leading question to help them explore further.\n"
                "4. Use plain text and ASCII math only (NO LaTeX math tags like \\frac, \\times, $$)."
            )
            payload = [HumanMessage(content=system_prompt)] + state["messages"]
            response = model.invoke(payload)
            return {"messages": [AIMessage(content=response.content)], "active_agent_node": "Surface Discussion Node"}
        except Exception as e:
            print(f"Gemini API error in surface_discussion_node: {e}")

    fallback = (
        f"Regarding your query on **{concept}** in {state.get('subject', 'the subject')}:\n\n"
        f"In {state.get('subject')} ({state.get('academic_tier')}), this concept explores the core principles of {concept}. "
        "What specific variable or idea would you like to analyze step by step?"
    )
    return {"messages": [AIMessage(content=fallback)], "active_agent_node": "Surface Discussion Node"}


def deep_discussion_node(state: AgentState):
    api_key = get_gemini_api_key()
    context_str = "\n".join(state.get("retrieved_curriculum", []))
    current_q = state.get("current_question") or {}
    concept = current_q.get("concept") or state.get("subject", "Science")
    user_msg = state["messages"][-1].content if state.get("messages") else ""

    if api_key:
        try:
            model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.2, google_api_key=api_key)
            system_prompt = (
                f"You are an expert Academic Discussion Mentor in {state.get('subject', 'Physics')} ({state.get('academic_tier', 'Class 10')}).\n"
                f"CURRENT QUESTION CONTEXT: {current_q.get('text', '')}\n"
                f"CONCEPT: {concept}\n"
                f"VERIFIED TEXTBOOK CURRICULUM CONTEXT:\n{context_str}\n\n"
                "INSTRUCTION:\n"
                "The student submitted an in-depth analytical query.\n"
                "1. Provide a comprehensive breakdown matching their intellectual depth.\n"
                "2. Explicitly include relevant equations, vector/biological mechanisms, or derivations.\n"
                "3. Conclude with a challenging follow-up question or advanced edge-case scenario.\n"
                "4. Use plain text and ASCII math only (NO LaTeX math tags like \\frac, \\times, $$)."
            )
            payload = [HumanMessage(content=system_prompt)] + state["messages"]
            response = model.invoke(payload)
            return {"messages": [AIMessage(content=response.content)], "active_agent_node": "Deep Inquiry Discussion Node"}
        except Exception as e:
            print(f"Gemini API error in deep_discussion_node: {e}")

    fallback = (
        f"Analyzing your inquiry regarding **{concept}** in {state.get('subject')}:\n\n"
        f"• **Governing Principle**: At the {state.get('academic_tier')} level, {concept} provides the structural foundation for understanding system dynamics in {state.get('subject')}.\n"
        f"• **Application**: Consider how the given parameters interact under these governing rules.\n\n"
        "Would you like to explore an edge case or work through a detailed derivation?"
    )
    return {"messages": [AIMessage(content=fallback)], "active_agent_node": "Deep Inquiry Discussion Node"}


def direct_explanation_node(state: AgentState):
    api_key = get_gemini_api_key()
    context_str = "\n".join(state.get("retrieved_curriculum", []))
    current_q = state.get("current_question") or {}
    subject = state.get("subject", "Physics")
    concept = current_q.get("concept", "Core Concept")
    curated_sol = current_q.get("solution")

    if api_key:
        try:
            model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.1, google_api_key=api_key)
            system_prompt = (
                f"DIRECT SOLUTION REQUESTED: The user asked for the direct answer or solution to a problem in {subject} ({state.get('academic_tier')}).\n"
                f"CURRENT QUESTION: {current_q.get('text', '')}\n"
                f"CONCEPT: {concept}\n"
                f"VERIFIED CURRICULUM CONTEXT:\n{context_str}\n\n"
                "CRITICAL INSTRUCTION:\n"
                "1. State the EXPLICIT DIRECT ANSWER in bold on line 1 (e.g. **Direct Answer: [result]**).\n"
                "2. Show the step-by-step formula and calculation walkthrough.\n"
                "3. Use plain text and ASCII math only (NO LaTeX math tags like \\frac, \\times, $$).\n"
                "4. Give the concrete answer specifically to the question asked."
            )
            payload = [HumanMessage(content=system_prompt)] + state["messages"]
            response = model.invoke(payload)
            return {"messages": [AIMessage(content=response.content)], "active_agent_node": "Direct Explainer Node"}
        except Exception as e:
            print(f"Gemini API error in direct_explanation_node: {e}")

    # Dynamic question-aware full solution fallback
    if curated_sol:
        fallback = (
            f"**⚡ Full Solution & Direct Answer ({concept})**:\n\n"
            f"{curated_sol}"
        )
    else:
        fallback = (
            f"**⚡ Full Solution & Direct Answer ({concept})**:\n\n"
            f"• **Subject**: {subject} ({state.get('academic_tier')})\n"
            f"• **Key Concept**: {concept}\n"
            f"• **Approach**: Review the governing rules for {concept} to resolve this problem."
        )
    return {"messages": [AIMessage(content=fallback)], "active_agent_node": "Direct Explainer Node"}


def route_after_analysis(state: AgentState) -> Literal["surface_discussion", "deep_discussion", "direct_explanation", "socratic_hint"]:
    depth = state.get("depth_level", "surface")
    if depth in ["solution", "remedial"]:
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
        "surface_discussion": "surface_discussion",
        "deep_discussion": "deep_discussion",
        "direct_explanation": "direct_explanation",
        "socratic_hint": "socratic_hint"
    }
)
workflow.add_edge("surface_discussion", END)
workflow.add_edge("deep_discussion", END)
workflow.add_edge("direct_explanation", END)
workflow.add_edge("socratic_hint", END)

compiled_tutor_app = workflow.compile()
