"""
Two-phase ingestion tests.

The pipeline must never publish a half-empty course. Phase A writes grounded
deterministic theory for *every* detected chapter and publishes the course at
once; Phase B then selectively upgrades a bounded number of chapters with the
local Llama, re-publishing after each one so an interrupted build keeps its work.

These tests drive the real worker functions with a stubbed question generator,
so no model, network call, vector store write or course file is touched.
"""
import copy
import os
import sys
import types

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import pytest  # noqa: E402

import app as app_module  # noqa: E402

PROSE = ("Thermodynamics couples heat, work and internal energy through state "
         "variables such as pressure, volume and temperature. ")


def _book(chapters: int = 6) -> str:
    """A markdown-style book: `# Chapter n: Title` headings plus prose."""
    out = ["# A Short Book of Physics\n"]
    for n in range(1, chapters + 1):
        out.append(f"\n# Chapter {n}: Topic {n}\n\n{PROSE * 10}\n")
    return "".join(out)


def _chapter_list(count: int = 6, enriched: int = 0) -> list:
    return [{
        "chapter_index": i,
        "chapter_id": f"ch_{i}",
        "title": f"Chapter {i}: Topic {i}",
        "full_text": PROSE * 10,
        "summary": f"Summary {i}",
        "objectives": [f"Objective {i}"],
        "cards": [{"topic": f"Topic {i}", "question": "Q?", "answer": "A."}],
        "deep_theory": {"overview": f"Topic {i}"},
        "theory_source": "llm" if i <= enriched else "deterministic",
    } for i in range(1, count + 1)]


class StubQGE:
    """Instant `QuestionGeneratorEngine` stand-in that records every call."""

    def __init__(self, fail_on: int = None):
        self.calls = []           # [(chapter_index, use_llm, include_cards)]
        self.fail_on = fail_on

    def generate_chapter_theory_and_cards(self, chapter_title, chapter_text,
                                          subject="General", tier="Standard",
                                          chapter_index=1, use_llm=True,
                                          allow_cloud_fallback=True,
                                          include_cards=True):
        if use_llm and self.fail_on is not None and chapter_index == self.fail_on:
            raise RuntimeError("simulated crash mid-enrichment")
        self.calls.append((chapter_index, use_llm, include_cards))
        return {
            "chapter_index": chapter_index,
            "title": chapter_title,
            "summary": f"Summary of {chapter_title}",
            "objectives": [f"Objective for {chapter_title}"],
            "cards": [{"topic": chapter_title, "question": "Q?", "answer": "A."}],
            "deep_theory": {"overview": chapter_title},
            "theory_source": "llm" if use_llm else "deterministic",
        }

    @property
    def llm_calls(self) -> list:
        return [c[0] for c in self.calls if c[1]]

    def generate_assessment_items(self, course_title, chapters,
                                  subject="General", tier="Standard"):
        return {
            "quizzes": [{"text": f"Quiz for {chapters[0]['title']}",
                         "concept": chapters[0]["title"]}] if chapters else [],
            "finalExam": [{"text": f"Exam for {course_title}", "expected": "1",
                           "formula": "E = 1"}],
        }


@pytest.fixture
def harness(monkeypatch):
    """Real workers + stubbed model + captured (never written) publications."""
    stub = StubQGE()
    publishes = []

    def _capture(record):
        publishes.append(copy.deepcopy(record))
        return record.get("course_id")

    monkeypatch.setattr(app_module, "QuestionGeneratorEngine", lambda *a, **k: stub)
    monkeypatch.setattr(app_module, "_persist_course", _capture)
    monkeypatch.setattr(
        app_module, "get_db_pipeline",
        lambda *a, **k: types.SimpleNamespace(ingest_custom_chunks=lambda **kw: None))
    return types.SimpleNamespace(stub=stub, publishes=publishes)


def test_select_chapters_for_llm_semantics():
    chapters = _chapter_list(6)
    assert app_module._select_chapters_for_llm(chapters, 0) == set()          # structure only
    assert app_module._select_chapters_for_llm(chapters, None) == {1, 2, 3, 4, 5, 6}
    assert app_module._select_chapters_for_llm(chapters, "1-2") == {1, 2}
    assert app_module._select_chapters_for_llm(chapters, 3) == {1, 2, 3}
    assert app_module._select_chapters_for_llm(chapters, "junk") == {1, 2, 3, 4, 5, 6}


def test_phase_a_publishes_every_chapter_without_any_model_work(harness):
    record = app_module.process_and_ingest_material(
        title="Two Phase Physics", subject="Physics",
        academic_tier="Undergraduate", raw_text=_book(6),
        course_id="custom_tst_phasea", enrich_count=0)

    chapters = record["chapters"]
    assert len(chapters) == 6                       # never a 1-of-6 partial build
    assert all(ch["summary"] and ch["deep_theory"] for ch in chapters)
    assert {ch["theory_source"] for ch in chapters} == {"deterministic"}
    assert record["theory_coverage"]["enriched_count"] == 0
    assert record["theory_coverage"]["chapters_total"] == 6
    assert record["theory_coverage"]["complete"] is False
    assert harness.stub.llm_calls == []             # Phase B skipped entirely


def test_phase_b_enriches_only_the_selected_chapters_progressively(harness):
    record = app_module.process_and_ingest_material(
        title="Selective Physics", subject="Physics",
        academic_tier="Undergraduate", raw_text=_book(6),
        course_id="custom_tst_select", enrich_chapters="1-2")

    enriched = [ch["chapter_index"] for ch in record["chapters"]
                if ch["theory_source"] == "llm"]
    assert enriched == [1, 2]
    assert harness.stub.llm_calls == [1, 2]
    # Skeleton publish + one re-publish per enriched chapter.
    assert len(harness.publishes) >= 3
    assert harness.publishes[0]["theory_coverage"]["enriched_count"] == 0
    assert record["theory_coverage"] == {
        "enriched_chapters": [1, 2], "enriched_count": 2, "chapters_total": 6,
        "pending_count": 4, "complete": False}


def test_interrupted_enrichment_never_loses_the_book(harness):
    """A crash mid-Phase-B must leave a complete, studyable course behind."""
    harness.stub.fail_on = 2
    with pytest.raises(RuntimeError):
        app_module.process_and_ingest_material(
            title="Interrupted Physics", subject="Physics",
            academic_tier="Undergraduate", raw_text=_book(6),
            course_id="custom_tst_interrupt", enrich_count=3)

    last = harness.publishes[-1]
    assert len(last["chapters"]) == 6                    # whole book survived
    assert last["theory_coverage"]["enriched_count"] == 1  # chapter 1's work kept
    assert harness.stub.llm_calls == [1]


def _course_record(count: int = 6, enriched: int = 0) -> dict:
    return {
        "course_id": "custom_tst_enrich",
        "title": "Enrich Physics",
        "subject": "Physics",
        "academic_tier": "Undergraduate",
        "chapters": _chapter_list(count, enriched),
        "cards": [], "quizzes": [], "finalExam": [],
        "theory_coverage": {
            "enriched_chapters": list(range(1, enriched + 1)),
            "enriched_count": enriched,
            "chapters_total": count,
            "pending_count": count - enriched,
            "complete": count > 0 and enriched >= count,
        },
    }


def test_enrich_worker_resumes_and_never_repeats_model_work(harness, monkeypatch):
    # A tiny in-memory course store: publishing writes back, exactly like the
    # real CourseManager does, which is what makes `resume` deterministic.
    store = {"course": _course_record(6, enriched=2)}

    def _persist(record):
        store["course"] = copy.deepcopy(record)
        harness.publishes.append(copy.deepcopy(record))
        return record.get("course_id")

    monkeypatch.setattr(app_module, "_persist_course", _persist)
    monkeypatch.setattr(app_module.CourseManager, "get_course_by_id",
                        lambda course_id: copy.deepcopy(store["course"]))
    app_module.INGESTION_JOBS["job_enrich_test"] = {
        "job_id": "job_enrich_test", "course_id": store["course"]["course_id"],
        "status": "queued", "progress": 0, "error": None}

    app_module._async_enrich_worker(job_id="job_enrich_test",
                                    course_id=store["course"]["course_id"],
                                    enrich_count=10, resume=True)

    assert harness.stub.llm_calls == [3, 4, 5, 6]        # 1-2 skipped, not redone
    published = harness.publishes[-1]
    assert published["theory_coverage"]["enriched_count"] == 6
    assert published["theory_coverage"]["complete"] is True
    job = app_module.INGESTION_JOBS["job_enrich_test"]
    assert job["status"] == "completed"
    assert job["chapters_enriched"] == 6                 # cumulative for the UI
    assert job["chapters_total"] == 6
    assert job["progress"] == 100

    # A finished course must never spend another model call.
    harness.publishes.clear()
    app_module._async_enrich_worker(job_id="job_enrich_test",
                                    course_id=store["course"]["course_id"],
                                    enrich_count=10, resume=True)
    assert harness.stub.llm_calls == [3, 4, 5, 6]
    assert harness.publishes == []
    assert app_module.INGESTION_JOBS["job_enrich_test"]["current_message"] == \
        "Nothing left to enrich."

    app_module.INGESTION_JOBS.pop("job_enrich_test", None)
