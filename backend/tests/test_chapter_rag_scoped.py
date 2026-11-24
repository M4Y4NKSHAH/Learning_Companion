import os
import sys
import uuid
import pytest

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from database_ingest import DatabaseIngestPipeline
from fastapi.testclient import TestClient
import app as app_module


@pytest.fixture(scope="module")
def temp_pipeline(tmp_path_factory):
    """Creates a temporary ChromaDB instance isolated to the test run."""
    tmp_dir = tmp_path_factory.mktemp("chroma_test_scoped")
    pipeline = DatabaseIngestPipeline(db_path=str(tmp_dir))
    return pipeline


def test_chapter_scoped_isolation(temp_pipeline):
    """
    Verifies that chunks indexed in chapter 1 and chapter 2 remain strictly isolated,
    and chapter-scoped queries return only relevant chapter context with zero crosstalk.
    """
    course_id = f"test_course_{uuid.uuid4().hex[:6]}"

    # Chapter 1: Classical Newtonian Mechanics
    ch1_chunks = [
        "Newton's First Law states that an object at rest remains at rest unless acted on by a net external force.",
        "Newton's Second Law defines force as the time rate of change of momentum, simplified to F = m * a.",
        "Newton's Third Law states that for every action force there is an equal and opposite reaction force."
    ]

    # Chapter 2: Quantum Wave-Particle Duality
    ch2_chunks = [
        "The de Broglie hypothesis proposes that particles of matter exhibit wave properties with wavelength lambda = h / p.",
        "Heisenberg's Uncertainty Principle states that position and momentum cannot simultaneously be measured with arbitrary precision: Delta x * Delta p >= hbar / 2.",
        "The Schrodinger wave equation describes the quantum mechanical state wavefunction Psi of a system over time."
    ]

    # Ingest chapter 1
    count1 = temp_pipeline.ingest_custom_chunks(
        course_id=course_id,
        chunks=ch1_chunks,
        subject="Physics",
        academic_tier="Undergraduate",
        chapter_id="ch_1",
        chapter_index=1,
        chapter_title="Chapter 1: Classical Mechanics"
    )
    assert count1 == 3

    # Ingest chapter 2
    count2 = temp_pipeline.ingest_custom_chunks(
        course_id=course_id,
        chunks=ch2_chunks,
        subject="Physics",
        academic_tier="Undergraduate",
        chapter_id="ch_2",
        chapter_index=2,
        chapter_title="Chapter 2: Quantum Physics"
    )
    assert count2 == 3

    # 1. Query Chapter 1 specifically for physics laws
    ch1_results = temp_pipeline.query_chapter_context(
        query="What is the equation for force?",
        course_id=course_id,
        chapter_id="ch_1",
        n_results=3
    )
    assert len(ch1_results) > 0
    # Must contain Newtonian laws, MUST NOT leak quantum mechanics
    for doc in ch1_results:
        assert "Newton" in doc or "force" in doc.lower()
        assert "Schrodinger" not in doc
        assert "Heisenberg" not in doc

    # 2. Query Chapter 2 specifically for wave mechanics
    ch2_results = temp_pipeline.query_chapter_context(
        query="Explain wave-particle duality and uncertainty",
        course_id=course_id,
        chapter_id="ch_2",
        n_results=3
    )
    assert len(ch2_results) > 0
    # Must contain Quantum laws, MUST NOT leak Newtonian laws
    for doc in ch2_results:
        assert "de Broglie" in doc or "Heisenberg" in doc or "Schrodinger" in doc or "wave" in doc.lower()
        assert "Newton's" not in doc

    # 3. Hybrid search scoped to Chapter 1
    hybrid_ch1 = temp_pipeline.query_hybrid(
        query="F = m * a net external force",
        course_id=course_id,
        chapter_id="ch_1",
        n_results=2
    )
    assert len(hybrid_ch1) > 0
    assert any("F = m * a" in d for d in hybrid_ch1)
    assert all("Schrodinger" not in d for d in hybrid_ch1)

    # 4. Hybrid search scoped to Chapter 2
    hybrid_ch2 = temp_pipeline.query_hybrid(
        query="Delta x * Delta p uncertainty principle",
        course_id=course_id,
        chapter_id="ch_2",
        n_results=2
    )
    assert len(hybrid_ch2) > 0
    assert any("Uncertainty Principle" in d for d in hybrid_ch2)
    assert all("Newton" not in d for d in hybrid_ch2)


def test_chapter_id_normalization(temp_pipeline):
    """
    Verifies that querying with chapter_id='ch_1', '1', or chapter_index=1 all successfully resolve.
    """
    course_id = f"test_norm_{uuid.uuid4().hex[:6]}"
    chunks = [
        "Thermodynamics Zeroth Law defines thermal equilibrium and temperature scale consistency."
    ]
    temp_pipeline.ingest_custom_chunks(
        course_id=course_id,
        chunks=chunks,
        subject="Physics",
        academic_tier="Class 11-12",
        chapter_id="ch_1",
        chapter_index=1,
        chapter_title="Chapter 1: Thermal Physics"
    )

    # Query using 'ch_1'
    res_ch1 = temp_pipeline.query_chapter_context(
        query="temperature thermal equilibrium",
        course_id=course_id,
        chapter_id="ch_1"
    )
    assert len(res_ch1) > 0
    assert "Zeroth Law" in res_ch1[0]

    # Query using raw '1'
    res_raw1 = temp_pipeline.query_chapter_context(
        query="temperature thermal equilibrium",
        course_id=course_id,
        chapter_id="1"
    )
    assert len(res_raw1) > 0
    assert "Zeroth Law" in res_raw1[0]

    # Query using chapter_index=1
    res_idx1 = temp_pipeline.query_chapter_context(
        query="temperature thermal equilibrium",
        course_id=course_id,
        chapter_index=1
    )
    assert len(res_idx1) > 0
    assert "Zeroth Law" in res_idx1[0]


def test_health_and_navigation_endpoints():
    """
    Verifies that the /health, /, and /api/tutor/chapter-context endpoints work properly.
    """
    client = TestClient(app_module.app)

    # Test /health
    health_res = client.get("/health")
    assert health_res.status_code == 200
    data = health_res.json()
    assert data["status"] == "healthy"
    assert "LearnerHelp" in data["service"]

    # Test /api/health
    api_health_res = client.get("/api/health")
    assert api_health_res.status_code == 200
    assert api_health_res.json()["status"] == "healthy"

    # Test / root
    root_res = client.get("/")
    assert root_res.status_code == 200
    assert root_res.json()["status"] == "online"

    # Test /api/tutor/chapter-context
    ctx_res = client.post("/api/tutor/chapter-context", json={
        "query": "Newton force acceleration",
        "subject": "Physics",
        "academic_tier": "Class 10",
        "n_results": 2
    })
    assert ctx_res.status_code == 200
    ctx_data = ctx_res.json()
    assert "results" in ctx_data
    assert "count" in ctx_data


def test_strict_chapter_isolation_no_crosstalk(temp_pipeline):
    """
    Verifies that when allow_fallback=False (default), querying chapter 2 for a concept
    only present in chapter 1 returns 0 chunks and NEVER leaks chapter 1 content.
    """
    course_id = f"test_isolation_{uuid.uuid4().hex[:6]}"

    # Chapter 1: Photosynthesis in plants
    temp_pipeline.ingest_custom_chunks(
        course_id=course_id,
        chunks=[
            "Chloroplasts contain chlorophyll pigments that absorb blue and red photons during the light-dependent reactions."
        ],
        subject="Biology",
        academic_tier="Undergraduate",
        chapter_id="ch_1",
        chapter_index=1,
        chapter_title="Chapter 1: Photosynthesis"
    )

    # Chapter 2: Human Cardiovascular System
    temp_pipeline.ingest_custom_chunks(
        course_id=course_id,
        chunks=[
            "The human heart is a four-chambered muscular organ consisting of two atria and two ventricles."
        ],
        subject="Biology",
        academic_tier="Undergraduate",
        chapter_id="ch_2",
        chapter_index=2,
        chapter_title="Chapter 2: Cardiovascular System"
    )

    # Query Chapter 2 for a photosynthesis concept with strict isolation
    ch2_results = temp_pipeline.query_chapter_context(
        query="What is the role of chlorophyll in chloroplasts?",
        course_id=course_id,
        chapter_id="ch_2",
        allow_fallback=False
    )
    # The result MUST NOT contain the Chapter 1 text
    for doc in ch2_results:
        assert "chlorophyll" not in doc.lower()
        assert "atria" in doc.lower() or "ventricles" in doc.lower() or "heart" in doc.lower()

    # Query Chapter 1 for heart with strict isolation
    ch1_results = temp_pipeline.query_chapter_context(
        query="How many chambers does the human heart have?",
        course_id=course_id,
        chapter_id="ch_1",
        allow_fallback=False
    )
    for doc in ch1_results:
        assert "ventricles" not in doc.lower()
        assert "atria" not in doc.lower()


def test_openstax_chapter_ingestion_multi_chapters(temp_pipeline, tmp_path):
    """
    Verifies that ingest_openstax_text accurately extracts and indexes multiple chapters
    even when chapter headers are short (< 40 characters) and preceded by a Table of Contents.
    """
    sample_text = (
        "Table of Contents\n\n"
        "CHAPTER 1\nIntroduction to Science 1\n\n"
        "CHAPTER 2\nKinematics 35\n\n"
        "CHAPTER 3\nDynamics 70\n\n"
        "Preface\nThis textbook is published under open educational licenses.\n\n"
        "CHAPTER 1\nIntroduction to Science\n\n"
        "Physics is the most fundamental of the sciences, describing matter and energy across all scales.\n\n"
        "Scientific methods emphasize observation, experimentation, hypothesis formulation, and empirical testing.\n\n"
        "CHAPTER 2\nKinematics\n\n"
        "Kinematics is the branch of classical mechanics that describes the motion of points, bodies, and systems.\n\n"
        "Displacement is the vector change in position of an object relative to a specified reference frame.\n\n"
        "CHAPTER 3\nDynamics\n\n"
        "Dynamics studies forces and torques and their effect on motion according to Newton's fundamental laws.\n\n"
        "Newton's Second Law mathematically equates net force to mass multiplied by linear acceleration (F = ma)."
    )

    book_file = tmp_path / "mock_physics.txt"
    book_file.write_text(sample_text, encoding="utf-8")

    temp_pipeline.ingest_openstax_text(
        file_path=str(book_file),
        subject="MockPhysics",
        academic_tier="Class 10"
    )

    # Verify Chapter 1 can be retrieved
    ch1_res = temp_pipeline.query_chapter_context(
        query="scientific methods observation experimentation",
        subject="MockPhysics",
        academic_tier="Class 10",
        chapter_id="ch_1"
    )
    assert len(ch1_res) > 0
    assert any("Scientific methods" in d or "fundamental" in d for d in ch1_res)

    # Verify Chapter 2 was NOT dropped and can be retrieved
    ch2_res = temp_pipeline.query_chapter_context(
        query="displacement vector position",
        subject="MockPhysics",
        academic_tier="Class 10",
        chapter_id="ch_2"
    )
    assert len(ch2_res) > 0
    assert any("Kinematics" in d or "Displacement" in d for d in ch2_res)

    # Verify Chapter 3 can be retrieved
    ch3_res = temp_pipeline.query_chapter_context(
        query="dynamics forces Newton Second Law",
        subject="MockPhysics",
        academic_tier="Class 10",
        chapter_id="ch_3"
    )
    assert len(ch3_res) > 0
    assert any("Dynamics" in d or "Second Law" in d for d in ch3_res)
