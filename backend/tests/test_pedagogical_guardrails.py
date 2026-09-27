import pytest
from langchain_core.messages import HumanMessage
from pedagogical_guardrails import (
    normalize_academic_tier,
    get_grade_level_guardrails,
    check_information_guardrails,
    construct_grounded_system_prompt,
    filter_for_grade_level,
)
from tutor_graph import compiled_tutor_app


def test_normalize_academic_tier():
    assert normalize_academic_tier("Class 9") == "introductory"
    assert normalize_academic_tier("Grade 10") == "introductory"
    assert normalize_academic_tier("Secondary") == "introductory"
    assert normalize_academic_tier("Beginner") == "introductory"
    
    assert normalize_academic_tier("Class 11") == "standard"
    assert normalize_academic_tier("Class 12") == "standard"
    assert normalize_academic_tier("Senior Secondary") == "standard"
    
    assert normalize_academic_tier("University") == "advanced"
    assert normalize_academic_tier("College") == "advanced"
    assert normalize_academic_tier("Advanced") == "advanced"


def test_grade_level_guardrails_class_9_vs_class_12():
    tier_9 = get_grade_level_guardrails("Class 9")
    tier_12 = get_grade_level_guardrails("Class 12")

    # Class 9 must strictly forbid calculus and college jargon
    assert any("calculus" in p.lower() for p in tier_9["strict_prohibitions"])
    assert any("analogy" in r.lower() for r in tier_9["mandatory_requirements"])

    # Class 12 must allow vector mechanics and calculus derivations
    assert "calculus" in tier_12["math_ceiling"].lower()


def test_check_information_guardrails_off_topic_deflection():
    off_topic_queries = [
        "What is the best gun in Fortnite?",
        "Can you play Minecraft with me?",
        "Which crypto coin should I buy today?",
        "Who is better, Messi or Ronaldo?",
        "Give me a recipe for chocolate cake"
    ]

    for q in off_topic_queries:
        is_valid, deflection = check_information_guardrails(
            student_query=q,
            course_title="Physics 101",
            chapter_title="Newton's Laws",
            subject="Physics"
        )
        assert is_valid is False
        assert deflection is not None
        assert "Physics 101" in deflection
        assert "Newton's Laws" in deflection


def test_check_information_guardrails_on_topic_permitted():
    academic_queries = [
        "Why does an object continue moving in space without friction?",
        "Can you explain Newton's second law with an example?",
        "How do I calculate acceleration when mass and force are known?",
        "What is inertia?"
    ]

    for q in academic_queries:
        is_valid, deflection = check_information_guardrails(
            student_query=q,
            course_title="Physics 101",
            chapter_title="Newton's Laws",
            subject="Physics"
        )
        assert is_valid is True
        assert deflection is None


def test_construct_grounded_system_prompt_primary_source():
    textbook_chunks = [
        "Section 3.1: Force is a push or pull upon an object resulting from interaction.",
        "Newton's Second Law: Acceleration of an object depends on the net force and mass (F = m * a)."
    ]

    prompt = construct_grounded_system_prompt(
        role="Socratic Academic Tutor",
        subject="Physics",
        tier_or_grade="Class 9",
        chapter_title="Laws of Motion",
        course_title="Secondary Physics",
        retrieved_textbook_chunks=textbook_chunks,
        current_question_context="What is the acceleration if F=10N and m=2kg?"
    )

    # Must contain primary ground truth header and chunks
    assert "PRIMARY GROUND TRUTH: INGESTED COURSE MATERIAL (TEXTBOOK)" in prompt
    assert "Section 3.1: Force is a push or pull" in prompt
    assert "NO calculus" in prompt
    assert "TARGET LEARNER LEVEL: Secondary / Class 9-10" in prompt


def test_filter_for_grade_level_post_generation():
    # In Class 9, calculus terms must be sanitized
    leaked_calculus_text = "The acceleration is defined as dv/dt, which is the derivative of velocity dy/dx."
    filtered = filter_for_grade_level(leaked_calculus_text, tier_or_grade="Class 9")
    
    assert "dv/dt" not in filtered
    assert "dy/dx" not in filtered
    assert "rate of change of speed" in filtered

    # In Class 12, calculus terms must be preserved
    kept_calculus = filter_for_grade_level(leaked_calculus_text, tier_or_grade="Class 12")
    assert "dv/dt" in kept_calculus
    assert "dy/dx" in kept_calculus


def test_tutor_graph_routes_off_topic_to_deflector():
    state = {
        "messages": [HumanMessage(content="Can you write a poem about Fortnite skins?")],
        "subject": "Physics",
        "academic_tier": "Class 9",
        "course_title": "Class 9 Physics",
        "chapter_title": "Force and Laws of Motion",
        "consecutive_errors": 0,
        "time_taken_seconds": 10
    }

    result = compiled_tutor_app.invoke(state)
    assert result["active_agent_node"] == "Course Guardrail Deflector"
    assert "Course Guardrail Notice" in result["messages"][-1].content
    assert "Force and Laws of Motion" in result["messages"][-1].content


def test_tutor_graph_hint_node_does_not_reveal_answer():
    state = {
        "messages": [HumanMessage(content="Can you give me a hint?")],
        "subject": "Physics",
        "academic_tier": "Class 9",
        "current_question": {
            "text": "Calculate the force on a 5kg mass accelerating at 2 m/s^2.",
            "concept": "Newton's Second Law",
            "expected_answer": "10 N",
            "hint": "Recall the formula connecting force, mass, and acceleration."
        },
        "inquiry_type": "hint",
        "consecutive_errors": 0,
        "time_taken_seconds": 15
    }

    result = compiled_tutor_app.invoke(state)
    assert result["active_agent_node"] == "Socratic Hint Node"
    # Never leaks the exact answer
    assert "10 N" not in result["messages"][-1].content
