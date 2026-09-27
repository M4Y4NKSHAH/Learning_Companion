import os
import sys
import tempfile
import pytest

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from hint_utils import compute_semantic_similarity
from spaced_repetition import SpacedRepetitionManager
from question_generator import QuestionGeneratorEngine
from material_parser import MaterialParser


def test_semantic_similarity():
    # 1. Exact match
    assert compute_semantic_similarity("PV = nRT", "PV = nRT") == 1.0
    assert compute_semantic_similarity("mitochondria", "Mitochondria") == 1.0

    # 2. Normalized match with answer prefix
    assert compute_semantic_similarity("ans = 42", "42") == 1.0
    assert compute_semantic_similarity("x = 50", "50") == 1.0

    # 3. Substring containment
    sim = compute_semantic_similarity("The ideal gas law equation is PV = nRT", "PV = nRT")
    assert sim >= 0.90

    # 4. Numerical tolerance (within 5%)
    sim_num = compute_semantic_similarity("8.31 J/(mol*K)", "8.314 J/(mol*K)")
    assert sim_num >= 0.90

    # 5. Semantic similarity via TF-IDF cosine
    sim_text = compute_semantic_similarity(
        "Energy of an isolated system is conserved over time",
        "Total energy remains conserved in an isolated system"
    )
    assert sim_text > 0.40

    # 6. Completely unrelated
    sim_unrelated = compute_semantic_similarity("Photosynthesis in green plants", "Newtonian gravitational constant")
    assert sim_unrelated < 0.20


def test_spaced_repetition_sm2():
    import uuid
    student_id = f"test_student_{uuid.uuid4().hex[:8]}"
    card_id = "card_thermo_001"

    # Review 1: Good recall (quality = 4) -> interval should be 1 day
    r1 = SpacedRepetitionManager.record_review(student_id, card_id, quality=4)
    assert r1["repetitions"] == 1
    assert r1["interval_days"] == 1
    assert r1["easiness_factor"] >= 2.5

    # Review 2: Perfect recall (quality = 5) -> interval should jump to 6 days
    r2 = SpacedRepetitionManager.record_review(student_id, card_id, quality=5)
    assert r2["repetitions"] == 2
    assert r2["interval_days"] == 6

    # Review 3: Lapse (quality = 1) -> repetitions reset to 0, interval resets to 1
    r3 = SpacedRepetitionManager.record_review(student_id, card_id, quality=1)
    assert r3["repetitions"] == 0
    assert r3["interval_days"] == 1

    # Check stats calculation
    stats = SpacedRepetitionManager.get_student_stats(student_id)
    assert stats["total_cards"] >= 1
    assert "due_today" in stats

    # Clean up test file
    file_path = SpacedRepetitionManager._get_student_file(student_id)
    if os.path.exists(file_path):
        os.remove(file_path)


def test_chapter_grounded_card_generation():
    chapter_text = """
    The Ideal Gas Law relates the pressure, volume, and temperature of an ideal gas.
    It is expressed as the equation: PV = nRT, where R is the ideal gas constant equal to 8.314 J/(mol*K).
    Boyle's Law states that at constant temperature, pressure is inversely proportional to volume: P1V1 = P2V2.
    Charles's Law states that volume is directly proportional to temperature at constant pressure.
    """

    qge = QuestionGeneratorEngine()
    result = qge.generate_chapter_theory_and_cards(
        chapter_title="Gas Laws and State Equations",
        chapter_text=chapter_text,
        subject="Physics",
        tier="Class 11",
        chapter_index=1
    )

    cards = result.get("cards", [])
    assert len(cards) >= 1
    
    # Verify cards are grounded in the chapter's actual concepts rather than generic boilerplate
    topics = [c["topic"].lower() for c in cards]
    assert any("pv" in t or "gas" in t or "boyle" in t or "charles" in t or "equation" in t for t in topics)
    assert not any("axioms" in t for t in topics)
