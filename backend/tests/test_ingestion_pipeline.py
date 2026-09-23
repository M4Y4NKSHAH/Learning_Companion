import os
import sys
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Load env variables
load_dotenv()

from material_parser import MaterialParser
from course_manager import CourseManager
from question_generator import QuestionGeneratorEngine
from database_ingest import DatabaseIngestPipeline

sample_lecture_notes = """
# Chapter 1: Introduction to Thermodynamics and Thermal Equilibrium

Thermodynamics is the branch of physics that deals with the relationships between heat, work, temperature, and energy.
The Zeroth Law of Thermodynamics establishes the concept of temperature as a fundamental state variable. If two systems are each in thermal equilibrium with a third system, they are in thermal equilibrium with each other.

Key properties include pressure (P), volume (V), temperature (T), and internal energy (U).
An ideal gas follows the equation of state: PV = nRT, where R is the universal gas constant (8.314 J/(mol*K)).

# Chapter 2: The First Law of Thermodynamics and Conservation of Energy

The First Law of Thermodynamics is an adaptation of the law of conservation of energy for thermodynamic systems.
It states that the change in internal energy (Delta U) of a closed system is equal to the heat added to the system (Q) minus the work done by the system on its surroundings (W):
Delta U = Q - W.

In an isobaric process, pressure remains constant, and work is calculated as W = P * Delta V.
In an isothermal process for an ideal gas, temperature remains constant, so Delta U = 0, meaning Q = W.
In an adiabatic process, no heat is exchanged with the environment (Q = 0), so Delta U = -W.

# Chapter 3: Heat Engines and the Second Law of Thermodynamics

The Second Law of Thermodynamics states that the total entropy of an isolated system always increases over time for spontaneous processes.
No heat engine operating in a cycle can convert all absorbed heat entirely into mechanical work (Kelvin-Planck statement).

The maximum theoretical efficiency of any heat engine operating between two thermal reservoirs is given by the Carnot efficiency:
Efficiency = 1 - (T_cold / T_hot), where temperatures must be expressed in absolute Kelvin.
"""

def run_smoke_test():
    print("=== 1. Testing Material Parser ===")
    clean_text = MaterialParser.clean_text(sample_lecture_notes)
    chapters = MaterialParser.detect_outline_or_chapters(clean_text)
    print(f"Detected {len(chapters)} chapters:")
    for ch in chapters:
        print(f" - [{ch['chapter_index']}] {ch['title']} (Length: {len(ch['content'])} chars)")
    
    assert len(chapters) == 3, f"Expected 3 chapters, got {len(chapters)}"

    print("\n=== 2. Testing QGE Chapter Theory & Flashcards ===")
    qge = QuestionGeneratorEngine()
    first_ch = chapters[0]
    theory_out = qge.generate_chapter_theory_and_cards(
        chapter_title=first_ch["title"],
        chapter_text=first_ch["content"],
        subject="Physics",
        tier="Undergraduate",
        chapter_index=1
    )
    print(f"Summary: {theory_out['summary']}")
    print(f"Objectives: {theory_out['objectives']}")
    print(f"Generated {len(theory_out['cards'])} flashcards:")
    for card in theory_out["cards"]:
        print(f"   Card: {card['topic']} | Q: {card['question'][:50]}...")

    assert len(theory_out["cards"]) >= 1

    print("\n=== 3. Testing QGE Assessment Generation ===")
    assessment_out = qge.generate_assessment_items(
        course_title="Thermodynamics 101",
        chapters=chapters,
        subject="Physics",
        tier="Undergraduate"
    )
    print(f"Generated {len(assessment_out['quizzes'])} quizzes:")
    for q in assessment_out["quizzes"]:
        print(f"   Quiz: {q.get('text')[:60]}... | Concept: {q.get('concept')}")

    print(f"Generated {len(assessment_out['finalExam'])} final exam questions:")
    for exam_q in assessment_out["finalExam"]:
        print(f"   Exam: {exam_q.get('text')[:60]}... | Expected: {exam_q.get('expected')} | Formula: {exam_q.get('formula')}")

    assert len(assessment_out["finalExam"]) >= 1

    print("\n=== 4. Testing Course Persistence ===")
    course_data = {
        "course_id": "test_thermo_custom_101",
        "title": "Thermodynamics 101",
        "subject": "Physics",
        "academic_tier": "Undergraduate",
        "chapters": chapters,
        "cards": theory_out["cards"],
        "quizzes": assessment_out["quizzes"],
        "finalExam": assessment_out["finalExam"]
    }
    saved_id = CourseManager.save_custom_course(course_data)
    print(f"Saved custom course: {saved_id}")
    
    fetched = CourseManager.get_course_by_id(saved_id)
    assert fetched is not None
    assert fetched["title"] == "Thermodynamics 101"
    print(f"Fetched course successfully: {fetched['title']} with {len(fetched['chapters'])} chapters.")
    
    # Clean up test course
    CourseManager.delete_custom_course(saved_id)
    print("Cleaned up test course.")

    print("\n>>> ALL INGESTION & PIPELINE TESTS PASSED SUCCESSFULY! <<<")

if __name__ == "__main__":
    run_smoke_test()
