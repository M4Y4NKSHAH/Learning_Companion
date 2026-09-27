import os
import sys
import pytest

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from database_ingest import SimpleBM25, DatabaseIngestPipeline
from analytics_db import AnalyticsDatabase


def test_simple_bm25_ranking():
    docs = [
        "Photosynthesis occurs in plant chloroplasts and uses sunlight to produce glucose.",
        "Thermodynamic state equation relates ideal gas variables: PV = nRT where R is constant.",
        "Classical Newtonian mechanics defines force as mass times acceleration F = m * a."
    ]

    bm25 = SimpleBM25(docs)
    scores = bm25.get_scores("PV = nRT ideal gas equation")
    
    # Doc 1 (index 1) has the exact formula PV = nRT and key words
    assert scores[1] > scores[0]
    assert scores[1] > scores[2]

    scores_fma = bm25.get_scores("force mass acceleration F = m * a")
    assert scores_fma[2] > scores_fma[0]
    assert scores_fma[2] > scores_fma[1]


def test_analytics_database_flow():
    import uuid
    student_id = f"test_student_{uuid.uuid4().hex[:8]}"
    course_id = f"course_phy_{uuid.uuid4().hex[:4]}"

    # Attempt 1: Correct attempt on chapter 1
    AnalyticsDatabase.record_attempt(
        student_id=student_id,
        course_id=course_id,
        chapter_id="ch_1",
        question_id="q_1",
        is_correct=True,
        accuracy_pct=95.0,
        fuzzy_score=92.0,
        error_severity=0.0,
        hint_level=1,
        latency_seconds=12.5
    )

    # Attempt 2: Incorrect attempt on chapter 2
    AnalyticsDatabase.record_attempt(
        student_id=student_id,
        course_id=course_id,
        chapter_id="ch_2",
        question_id="q_2",
        is_correct=False,
        accuracy_pct=30.0,
        fuzzy_score=40.0,
        error_severity=0.6,
        hint_level=2,
        latency_seconds=25.0
    )

    # Verify heatmap
    heatmap = AnalyticsDatabase.get_course_mastery_heatmap(student_id, course_id)
    assert len(heatmap) == 2
    ch1 = next(h for h in heatmap if h["chapter_id"] == "ch_1")
    ch2 = next(h for h in heatmap if h["chapter_id"] == "ch_2")
    assert ch1["correct_attempts"] == 1
    assert ch1["avg_fuzzy_score"] >= 90.0
    assert ch2["correct_attempts"] == 0
    assert ch2["avg_fuzzy_score"] <= 50.0

    # Verify summary
    summary = AnalyticsDatabase.get_student_summary(student_id)
    assert summary["total_attempts"] >= 2
    assert summary["accuracy_rate"] == 50.0
