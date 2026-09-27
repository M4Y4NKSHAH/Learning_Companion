import os
import sys

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from question_generator import QuestionGeneratorEngine
from material_parser import MaterialParser

def test_fact_extraction():
    text = (
        "Newton's Second Law states that force equals mass times acceleration (F = m * a). "
        "An ideal gas follows the equation of state: PV = nRT, where R is the universal gas constant of 8.314 J/(mol*K). "
        "In an isothermal process, Delta U = 0."
    )
    facts = QuestionGeneratorEngine._extract_facts_from_text(text)
    print("Extracted facts:", facts)
    assert len(facts) >= 2, f"Expected at least 2 facts, got {len(facts)}"
    
    # Check that equation or definition is caught
    types = [f["type"] for f in facts]
    assert "equation" in types or "definition" in types or "value" in types


def test_content_grounded_assessment_generation():
    chapters = [
        {
            "chapter_index": 1,
            "title": "Thermodynamics & Equilibrium",
            "full_text": (
                "The Zeroth Law of Thermodynamics establishes temperature as a fundamental state variable. "
                "The ideal gas equation is PV = nRT. The universal gas constant has a value of 8.314 J/(mol*K)."
            ),
            "content": "The Zeroth Law of Thermodynamics establishes temperature as a fundamental state variable. PV = nRT."
        },
        {
            "chapter_index": 2,
            "title": "The First Law of Thermodynamics",
            "full_text": (
                "The First Law states that change in internal energy is given by Delta U = Q - W. "
                "In an adiabatic process, heat exchanged Q = 0."
            ),
            "content": "The First Law states that Delta U = Q - W."
        }
    ]
    
    qge = QuestionGeneratorEngine()
    assessment = qge.generate_assessment_items(
        course_title="Thermodynamics Complete",
        chapters=chapters,
        subject="Physics",
        tier="Undergraduate"
    )
    
    quizzes = assessment["quizzes"]
    final_exam = assessment["finalExam"]
    
    assert len(quizzes) == 2, f"Expected 2 quizzes, got {len(quizzes)}"
    assert len(final_exam) == 2, f"Expected 2 exam questions, got {len(final_exam)}"
    
    # Verify quizzes are grounded (not generic template)
    q1 = quizzes[0]
    print(f"Quiz 1: {q1['text']} -> Correct: {q1['correct_answer']}")
    assert len(q1["options"]) == 4
    assert q1["correct_answer"] in q1["options"]
    
    # Verify final exam expected is not the old boilerplate "Governing principle of {ch_title}"
    for exam_q in final_exam:
        print(f"Exam: {exam_q['text']} -> Expected: '{exam_q['expected']}' | Formula: '{exam_q['formula']}'")
        assert not exam_q["expected"].startswith("Governing principle of"), \
            f"Expected concrete answer, got generic: {exam_q['expected']}"


def test_chunking_sliding_overlap():
    long_text = (
        "Sentence one explains the fundamental principle of classical mechanics. "
        "Sentence two introduces the role of inertia in resisting acceleration. "
        "Sentence three specifies the mathematical boundary conditions for equilibrium. "
        "Sentence four demonstrates how frictional forces counteract applied shear stresses. "
        "Sentence five derives the conservation laws under closed system constraints. "
        "Sentence six highlights common student misconceptions in kinetic dynamics."
    )
    chunks = MaterialParser.create_semantic_chunks(long_text, chunk_size=20, overlap=10)
    assert len(chunks) >= 2, f"Expected multiple chunks with small chunk_size, got {len(chunks)}"
    print(f"Generated {len(chunks)} chunks with sliding overlap.")


if __name__ == "__main__":
    test_fact_extraction()
    test_content_grounded_assessment_generation()
    test_chunking_sliding_overlap()
    print("\n>>> ALL CONTENT-AWARE QG & CHUNKER TESTS PASSED! <<<")
