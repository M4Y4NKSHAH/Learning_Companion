import os
import sys
import json
import time
import uuid
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv

# Ensure current backend directory is in sys.path for robust module resolution
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Load the .env file from current directory first, fallback to parent directory
local_env = os.path.join(backend_dir, ".env")
if os.path.exists(local_env):
    load_dotenv(dotenv_path=local_env)
else:
    load_dotenv()

import difflib
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from fuzzy_engine import FuzzyMarkingSystem
from analytics import PathPerformanceAnalytics
from theory_repo import FLASHCARD_REPOSITORY
from tutor_graph import compiled_tutor_app
from flashcard_builder import build_flashcards_from_chroma, generate_gemini_flashcards_from_chroma, _gemini_flashcard_cache
from hint_utils import sanitize_gap_analysis, sanitize_hint_text, HINT_FORMAT_DIRECTIVE, compute_semantic_similarity
from spaced_repetition import SpacedRepetitionManager
from material_parser import MaterialParser
from course_manager import CourseManager
from question_generator import QuestionGeneratorEngine
from database_ingest import DatabaseIngestPipeline, get_db_pipeline
from pedagogical_guardrails import filter_for_grade_level, normalize_academic_tier
from local_llm_service import local_llm
from divide_book import estimate_llm_build, parse_chapter_selection

app = FastAPI(title="Unified Agentic Socratic Tutoring Platform")

# Background job tracker for non-blocking asynchronous course ingestion
INGESTION_JOBS: dict[str, dict] = {}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API PAYLOAD SCHEMAS ---
class IngestMaterialPayload(BaseModel):
    title: str
    subject: str = "General"
    academic_tier: str = "Standard"
    raw_text: str = ""
    generate_questions_immediately: bool = True
    async_mode: bool = False
    # Selective synthesis: e.g. enrich_count=10 on a 41-chapter book synthesizes
    # LLM theory for the first 10 and the grounded skeleton for the rest.
    enrich_count: Optional[int] = None
    enrich_chapters: Optional[str] = None
    include_cards: bool = True
    resume: bool = False

class EnrichCoursePayload(BaseModel):
    """Asks a published course to enrich more chapters with the local Llama."""
    enrich_count: Optional[int] = None          # e.g. 10 -> first 10 remaining
    enrich_chapters: Optional[str] = None       # e.g. "11-20" or "1,3,5-8"
    include_cards: bool = True
    resume: bool = True                          # never redo already-enriched chapters

class ChatSessionPayload(BaseModel):
    message: str
    time_taken: int
    consecutive_errors: int
    current_tier: str
    current_subject: str
    course_id: Optional[str] = None
    chapter_id: Optional[str] = None
    history: list[dict] = []
    current_question: dict = {}
    inquiry_type: str = "discussion"
    hint_level: int = 1


class ShortAnswerPayload(BaseModel):
    question_text: str
    student_raw_input: str
    expected_answer: str
    seconds_spent: int
    attempts_count: int
    current_tier: str
    current_subject: str
    course_id: Optional[str] = None
    chapter_id: Optional[str] = None
    student_id: Optional[str] = "default_student"
    hint_formula: str = ""
    hint_misconception: str = ""
    hints_requested: int = 0
    hint_level: int = 1

class SRSReviewPayload(BaseModel):
    student_id: str
    card_id: str
    quality: int
    course_id: Optional[str] = None
    chapter_id: Optional[str] = None
    card_data: Optional[dict] = None

class ExamSubmissionPayload(BaseModel):
    correct_answers: int = 0
    total_questions: int = 0
    total_elapsed_time: int = 0
    current_tier: str
    current_subject: str
    course_id: Optional[str] = None
    student_id: Optional[str] = "default_student"
    mock_chat_history: list[dict] = []
    question_details: list[dict] = []

class TheoryRequestPayload(BaseModel):
    current_tier: str
    current_subject: str
    course_id: Optional[str] = None


# --- CORE RAG UTILITY FACTORY ---
def execute_rag_vector_lookup(subject: str, tier: str, query: str) -> list[str]:
    """
    Queries the background vector store infrastructure (ChromaDB collection) 
    to retrieve localized, verified semantic core chunks.
    """
    try:
        from database_ingest import DatabaseIngestPipeline
        pipeline = DatabaseIngestPipeline()
        results = pipeline.curriculum_collection.query(
            query_texts=[query],
            n_results=3,
            where={"$and": [{"academic_tier": tier}, {"subject": subject}]}
        )
        return results['documents'][0] if results and results.get('documents') else []
    except Exception:
        return [f"Core textbook reference material for {tier} level structural {subject} parameters."]

# --- MATERIAL INGESTION & PIPELINE HELPER ---
def _find_best_matching_chapter(target_title: str, raw_chapters: list[dict]) -> dict:
    """Finds the raw detected chapter whose title or content best correlates with the guided title."""
    if not raw_chapters:
        return {}
    target_clean = re.sub(r"^(?:Chapter|Unit|Module|Section)\s+\d+[:\s\-\.]*", "", target_title, flags=re.IGNORECASE).strip().lower()
    best_match = None
    best_score = -1.0
    for ch in raw_chapters:
        ch_title = ch.get("title", "")
        ch_clean = re.sub(r"^(?:Chapter|Unit|Module|Section)\s+\d+[:\s\-\.]*", "", ch_title, flags=re.IGNORECASE).strip().lower()
        score = difflib.SequenceMatcher(None, target_clean, ch_clean).ratio()
        if score > best_score:
            best_score = score
            best_match = ch
    return best_match if best_match else raw_chapters[0]


# --- MATERIAL INGESTION & PIPELINE HELPER ---
def _smart_divide_material(text: str, title: str, subject: str,
                           academic_tier: str,
                           extracted_book: Optional[Any] = None,
                           path: Optional[str] = None) -> list:
    """Book-agnostic division of an uploaded document.

    Infers this document's own chapter/section/unit layout (see
    `book_structurer`) instead of assuming one publisher's format, so uploaded
    PDFs, EPUB dumps, markdown notes and pasted text all divide correctly.
    Returns [] when the structure pass cannot beat the simple parser, which
    keeps the classic path available for very short material.
    """
    try:
        from divide_book import SmartBookDivider
        divider = SmartBookDivider(text=text, title=title, subject=subject,
                                   tier=academic_tier,
                                   extracted_book=extracted_book,
                                   path=path)
        if not divider.plan.chapter_matches or divider.plan.chapter_kind in ("none", "titled_caps"):
            return []
        chapters = divider.divide()
    except Exception as exc:
        print(f"[Ingestion] Smart division unavailable ({exc}); using simple detection.")
        return []
    if len(chapters) < 2:
        return []
    print(f"[Ingestion] Smart division found {len(chapters)} chapters "
          f"via '{divider.plan.chapter_kind}' / sections '{divider.plan.section_kind}'.")
    return chapters


def _select_chapters_for_llm(raw_chapters: list, enrich_spec) -> set:
    """Resolves which chapter numbers should get model-enriched theory.

    A full-book Llama pass is ~25 s per chapter, so the caller can cap the work
    (e.g. "10" out of 41). `None` means every chapter, which preserves the
    original behaviour for API clients that do not send a selection;
    `0` means no chapter — publish the grounded skeleton only.
    """
    if enrich_spec is not None:
        if (isinstance(enrich_spec, int) and enrich_spec == 0) or \
           (isinstance(enrich_spec, str) and enrich_spec.strip() == "0"):
            return set()
    available = [ch.get("chapter_index", i) for i, ch in enumerate(raw_chapters, 1)]
    selected = parse_chapter_selection(enrich_spec, available)
    targets = selected if selected is not None else available
    return set(targets)


def _theory_coverage(processed_chapters: list) -> dict:
    """Which chapters are Llama-enriched, out of how many (learned by the UI)."""
    enriched = [ch.get("chapter_index") for ch in processed_chapters
                if ch.get("theory_source") == "llm"]
    total = len(processed_chapters)
    return {
        "enriched_chapters": enriched,
        "enriched_count": len(enriched),
        "chapters_total": total,
        "pending_count": max(0, total - len(enriched)),
        "complete": total > 0 and len(enriched) >= total,
    }


def process_and_ingest_material(
    title: str,
    subject: str,
    academic_tier: str,
    raw_text: str,
    course_id: Optional[str] = None,
    job_id: Optional[str] = None,
    enrich_count: Optional[int] = None,
    enrich_chapters: Optional[str] = None,
    include_cards: bool = True,
    resume: bool = False,
    extracted_book: Optional[Any] = None,
    source_path: Optional[str] = None
) -> dict:
    """
    Enterprise Ingestion Pipeline — two-phase, so the learner never waits.

    Phase A (seconds): sanitize, divide, build the source-grounded deterministic
        theory for EVERY chapter, vectorize, and publish the course. It is
        complete and studyable immediately — chapters, sections, summaries,
        objectives and flashcards all exist.
    Phase B (minutes, optional): enrich only the selected chapters with the local
        Llama (`enrich_count` / `enrich_chapters`), re-publishing as each one
        lands so an interrupted run keeps its work. `resume=True` skips chapters
        that are already `theory_source == "llm"`.
    Phase C: content-grounded quizzes and the summative final exam.
    """

    if job_id and job_id in INGESTION_JOBS:
        INGESTION_JOBS[job_id]["status"] = "processing"
        INGESTION_JOBS[job_id]["current_step"] = 1
        INGESTION_JOBS[job_id]["current_message"] = "Parsing and sanitizing document content..."
        INGESTION_JOBS[job_id]["progress"] = 15

    clean_text = MaterialParser.clean_text(raw_text)
    if len(clean_text) < 50:
        raise HTTPException(status_code=400, detail="The provided material is too short to extract a curriculum.")

    # Auto-detect domain subject if title or text indicates a specific academic field
    detected_subject = MaterialParser.detect_subject(title, clean_text, fallback=subject)
    if detected_subject:
        subject = detected_subject

    # 1. Detect / Decompose into chapters dynamically (any layout, any length).
    # The smart divider infers this document's own heading style; the simple
    # parser remains as the fallback for very short or structure-less material.
    raw_chapters = _smart_divide_material(clean_text, title, subject, academic_tier,
                                          extracted_book=extracted_book, path=source_path)
    if not raw_chapters:
        raw_chapters = MaterialParser.detect_outline_or_chapters(clean_text, max_chapters=None)
    if not raw_chapters:
        raw_chapters = [{
            "chapter_index": 1,
            "title": f"{title} - Core Fundamentals",
            "content": clean_text,
            "subsections": []
        }]

    if not course_id:
        existing = CourseManager.find_course_by_title(title)
        if existing and not existing.get("is_builtin", False):
            course_id = existing["course_id"]
        else:
            course_id = f"custom_{subject.lower()[:3]}_{uuid.uuid4().hex[:6]}"

    total_raw = len(raw_chapters)
    if job_id and job_id in INGESTION_JOBS:
        INGESTION_JOBS[job_id]["course_id"] = course_id
        INGESTION_JOBS[job_id]["subject"] = subject
        INGESTION_JOBS[job_id]["total_chapters"] = total_raw
        INGESTION_JOBS[job_id]["current_step"] = 2
        INGESTION_JOBS[job_id]["current_message"] = f"Structured {total_raw} instructional chapters for {subject}. Initializing synthesis..."
        INGESTION_JOBS[job_id]["progress"] = 25

    spec = enrich_chapters if enrich_chapters is not None else enrich_count
    llm_targets = _select_chapters_for_llm(raw_chapters, spec)
    planned = len(llm_targets) if llm_targets else 0

    qge = QuestionGeneratorEngine()
    db_pipeline = get_db_pipeline()

    processed_chapters = []
    all_cards = []
    print(f"[Ingestion] Phase A: building deterministic theory for all "
          f"{total_raw} chapters (course openable immediately)...")

    for idx, ch in enumerate(raw_chapters, 1):
        ch_idx = ch.get("chapter_index", idx)
        ch_title = ch.get("title", f"Chapter {ch_idx}")
        # Smart division emits `full_text` + structured `section_texts`; the
        # classic parser emits `content`. Support both.
        ch_content = ch.get("content") or ch.get("full_text", "")
        ch_id = ch.get("chapter_id") or f"ch_{idx}"

        if job_id and job_id in INGESTION_JOBS:
            INGESTION_JOBS[job_id]["current_step"] = 3
            INGESTION_JOBS[job_id]["current_message"] = (
                f"Structuring Chapter {idx} of {total_raw}: {ch_title[:32]}...")
            INGESTION_JOBS[job_id]["progress"] = int(25 + ((idx - 0.5) / max(1, total_raw)) * 25)

        # Phase A is deliberately local/offline: every chapter gets the grounded
        # deterministic skeleton in milliseconds, so the course is complete now.
        theory_data = qge.generate_chapter_theory_and_cards(
            chapter_title=ch_title,
            chapter_text=ch_content[:9000],
            subject=subject,
            tier=academic_tier,
            chapter_index=ch_idx,
            use_llm=False,
            include_cards=include_cards,
        )

        ch_cards = theory_data.get("cards", [])
        all_cards.extend(ch_cards)

        processed_chapters.append({
            "chapter_id": ch_id,
            "chapter_index": ch_idx,
            "title": ch_title,
            "unit_index": ch.get("unit_index"),
            "unit_name": ch.get("unit_name"),
            "summary": theory_data.get("summary", ""),
            "objectives": theory_data.get("objectives", []),
            "cards": ch_cards,
            "deep_theory": theory_data.get("deep_theory", {}),
            "subsections": ch.get("subsections", []),
            "section_texts": ch.get("section_texts", []),
            "sections_count": ch.get("sections_count", len(ch.get("section_texts", []))),
            "toc_sections": ch.get("toc_sections", []),
            "theory_source": theory_data.get("theory_source", "deterministic"),
            "full_text": ch_content,
            "content_preview": ch_content[:400] + "..." if len(ch_content) > 400 else ch_content
        })

    # ---- Publish the complete skeleton course NOW: the learner can open it immediately (~1-2s) --- #
    course_record = _assemble_course_record(
        course_id, title, subject, academic_tier, processed_chapters,
        all_cards, quizzes=[], final_exam=[], enriched_count=0)
    _persist_course(course_record)
    print(f"[Ingestion] [{course_id}] published skeleton with all {total_raw} chapters "
          f"(grounded deterministic theory). Instantaneous Phase A publication complete.")

    if job_id and job_id in INGESTION_JOBS:
        INGESTION_JOBS[job_id]["course_ready"] = True
        INGESTION_JOBS[job_id]["course"] = course_record
        INGESTION_JOBS[job_id]["current_step"] = 3
        INGESTION_JOBS[job_id]["current_message"] = (
            f"Course ready to study! Now enriching {planned}/{total_raw} "
            f"chapter(s) with the local Llama..." if planned
            else "Course skeleton published instantaneously! Course is ready to study.")
        INGESTION_JOBS[job_id]["progress"] = 55
        if planned:
            INGESTION_JOBS[job_id]["chapters_total"] = total_raw
            INGESTION_JOBS[job_id]["chapters_enriched"] = 0
            INGESTION_JOBS[job_id]["eta_seconds"] = None

    # ---- Batch vectorize knowledge chunks into ChromaDB (non-blocking for course availability) --- #
    try:
        batch_items = []
        for ch in raw_chapters:
            ch_idx = ch.get("chapter_index", 1)
            ch_id = ch.get("chapter_id") or f"ch_{ch_idx}"
            ch_title = ch.get("title", f"Chapter {ch_idx}")
            ch_content = ch.get("content") or ch.get("full_text", "")
            chunks = MaterialParser.create_semantic_chunks(ch_content[:8000], chunk_size=400, overlap=40)[:15]
            if chunks:
                batch_items.append({
                    "course_id": course_id,
                    "chunks": chunks,
                    "subject": subject,
                    "academic_tier": academic_tier,
                    "chapter_id": ch_id,
                    "chapter_index": ch_idx,
                    "chapter_title": ch_title,
                })

        if hasattr(db_pipeline, "ingest_custom_chunks_batch"):
            db_pipeline.ingest_custom_chunks_batch(batch_items)
        else:
            for item in batch_items:
                db_pipeline.ingest_custom_chunks(**item)
    except Exception as ve:
        print(f"[ChromaDB] Vector ingestion warning: {ve}")

    # ---- Phase B: selective Llama enrichment with measured progress --------- #
    if planned:
        est = estimate_llm_build(planned)
        print(f"[Ingestion] Phase B: enriching {planned} chapter(s) "
              f"(~{est['minutes']} min at ~25 s/chapter), re-publishing each one "
              f"so work is never lost.")
        avg_seconds = None
        enriched_now = 0
        started_all = time.time()

        for ch in processed_chapters:
            num = ch["chapter_index"]
            if llm_targets and num not in llm_targets:
                continue
            if resume and ch.get("theory_source") == "llm":
                continue

            start = time.time()
            if job_id and job_id in INGESTION_JOBS:
                INGESTION_JOBS[job_id]["current_message"] = (
                    f"Enriching chapter {num} of {total_raw} "
                    f"with the local Llama (gold-star theory)...")
            theory_data = qge.generate_chapter_theory_and_cards(
                chapter_title=ch["title"],
                chapter_text=ch["full_text"][:9000],
                subject=subject,
                tier=academic_tier,
                chapter_index=num,
                use_llm=True,
                include_cards=include_cards,
                allow_cloud_fallback=False,
            )
            ch["summary"] = theory_data.get("summary", "")
            ch["objectives"] = theory_data.get("objectives", [])
            ch["cards"] = theory_data.get("cards", [])
            ch["deep_theory"] = theory_data.get("deep_theory", {})
            ch["theory_source"] = theory_data.get("theory_source", "deterministic")

            all_cards = [c for chh in processed_chapters for c in chh.get("cards", [])]
            enriched_now += 1
            elapsed = time.time() - start
            avg_seconds = (elapsed if avg_seconds is None
                           else (avg_seconds * (enriched_now - 1) + elapsed) / enriched_now)
            remaining = max(0, planned - enriched_now)
            eta_sec = int(remaining * avg_seconds) if avg_seconds else None
            eta_min = round(eta_sec / 60.0, 1) if eta_sec is not None else None
            print(f"[Ingestion]   chapter {num} enriched [{enriched_now}/{planned}] "
                  f"({avg_seconds:.1f}s/ch) -> re-published"
                  + (f" | ~{eta_min} min left" if eta_min is not None else ""))

            course_record["chapters"] = processed_chapters
            course_record["cards"] = all_cards
            course_record["flashcards_count"] = len(all_cards)
            course_record["theory_coverage"] = _theory_coverage(processed_chapters)
            _persist_course(course_record)

            if job_id and job_id in INGESTION_JOBS:
                INGESTION_JOBS[job_id]["chapters_enriched"] = enriched_now
                INGESTION_JOBS[job_id]["eta_seconds"] = eta_sec
                INGESTION_JOBS[job_id]["avg_seconds_per_chapter"] = round(avg_seconds, 1)
                INGESTION_JOBS[job_id]["progress"] = int(55 + (enriched_now / max(1, planned)) * 30)

        if enriched_now == 0:
            warning = (
                "No chapter could be enriched locally — every chapter keeps its "
                "grounded deterministic theory. Verify Ollama is running "
                "(`ollama serve`) and that a model is registered (`ollama list`).")
            print(f"[Ingestion] WARNING: {warning}")
            if job_id and job_id in INGESTION_JOBS:
                INGESTION_JOBS[job_id]["current_message"] = warning
    else:
        print("[Ingestion] Selective enrichment is disabled for this run; every "
              "chapter keeps the grounded deterministic skeleton.")

    # 3. Generate Content-Aware Assessment Items
    if job_id and job_id in INGESTION_JOBS:
        INGESTION_JOBS[job_id]["current_step"] = 5
        INGESTION_JOBS[job_id]["current_message"] = "Synthesizing chapter quizzes & summative final exam..."
        INGESTION_JOBS[job_id]["progress"] = 85

    assessment = qge.generate_assessment_items(
        course_title=title,
        chapters=processed_chapters,
        subject=subject,
        tier=academic_tier
    )

    quizzes = assessment.get("quizzes", [])
    final_exam = assessment.get("finalExam", [])

    # 4. Final assemble and persist (assessments + coverage + counts)
    course_record = _assemble_course_record(
        course_id, title, subject, academic_tier, processed_chapters,
        all_cards, quizzes=quizzes, final_exam=final_exam,
        enriched_count=_theory_coverage(processed_chapters)["enriched_count"])
    _persist_course(course_record)

    if job_id and job_id in INGESTION_JOBS:
        INGESTION_JOBS[job_id]["status"] = "completed"
        INGESTION_JOBS[job_id]["current_step"] = 5
        final_coverage = _theory_coverage(processed_chapters)
        INGESTION_JOBS[job_id]["current_message"] = (
            f"Course generated successfully! {final_coverage['enriched_count']}/"
            f"{final_coverage['chapters_total']} chapters carry Llama theory; "
            f"the rest use grounded deterministic theory.")
        INGESTION_JOBS[job_id]["progress"] = 100
        INGESTION_JOBS[job_id]["chapters_enriched"] = final_coverage["enriched_count"]
        INGESTION_JOBS[job_id]["chapters_total"] = final_coverage["chapters_total"]
        INGESTION_JOBS[job_id]["eta_seconds"] = 0
        INGESTION_JOBS[job_id]["course"] = course_record

    return course_record


def _assemble_course_record(course_id: str, title: str, subject: str,
                            academic_tier: str, processed_chapters: list,
                            all_cards: list, quizzes: Optional[list] = None,
                            final_exam: Optional[list] = None,
                            enriched_count: int = 0) -> dict:
    """Builds the persisted course envelope; reused for every progressive save."""
    units: List[Dict[str, Any]] = []
    for ch in processed_chapters:
        unit_idx = ch.get("unit_index")
        if unit_idx is None:
            continue
        if not any(u["unit_index"] == unit_idx for u in units):
            units.append({"unit_index": unit_idx,
                          "unit_name": ch.get("unit_name") or f"Unit {unit_idx}"})
    total = len(processed_chapters)
    return {
        "course_id": course_id,
        "title": title,
        "subject": subject,
        "academic_tier": academic_tier,
        "is_builtin": False,
        "description": (f"Custom ingested curriculum for {title}. "
                        f"Llama-enriched chapters: {enriched_count}/{total}."),
        "theory_coverage": {
            "enriched_chapters": [ch.get("chapter_index") for ch in processed_chapters
                                  if ch.get("theory_source") == "llm"],
            "enriched_count": enriched_count,
            "chapters_total": total,
            "pending_count": max(0, total - enriched_count),
            "complete": total > 0 and enriched_count >= total,
        },
        "chapters_count": len(processed_chapters),
        "sections_count": sum(ch.get("sections_count", 0) for ch in processed_chapters),
        "unit_count": len(units),
        "units": sorted(units, key=lambda u: u["unit_index"]),
        "flashcards_count": len(all_cards),
        "quizzes_count": len(quizzes or []),
        "exam_questions_count": len(final_exam or []),
        "chapters": processed_chapters,
        "cards": all_cards,
        "quizzes": quizzes or [],
        "finalExam": final_exam or [],
    }


def _persist_course(course_record: dict) -> str:
    """Writes the course JSON; full-text is capped for payload hygiene."""
    try:
        from divide_book import slim_course_source_text
        slim_course_source_text(course_record)
    except Exception:
        pass
    return CourseManager.save_custom_course(course_record)


def _async_ingest_worker(
    job_id: str,
    title: str,
    subject: str,
    academic_tier: str,
    raw_text: str,
    course_id: str,
    enrich_count: Optional[int] = None,
    enrich_chapters: Optional[str] = None,
    include_cards: bool = True,
    resume: bool = False,
    extracted_book: Optional[Any] = None,
    source_path: Optional[str] = None
):
    """Background worker executing dynamic ingestion without blocking web responses."""
    try:
        process_and_ingest_material(
            title=title,
            subject=subject,
            academic_tier=academic_tier,
            raw_text=raw_text,
            course_id=course_id,
            job_id=job_id,
            enrich_count=enrich_count,
            enrich_chapters=enrich_chapters,
            include_cards=include_cards,
            resume=resume,
            extracted_book=extracted_book,
            source_path=source_path
        )
    except Exception as e:
        print(f"[Async Ingestion Worker] Error processing {title}: {e}")
        if job_id in INGESTION_JOBS:
            INGESTION_JOBS[job_id]["status"] = "failed"
            INGESTION_JOBS[job_id]["error"] = str(e)


# --- INGESTION & COURSE REST ENDPOINTS ---

@app.post("/api/material/ingest")
async def ingest_material_json(payload: IngestMaterialPayload, background_tasks: BackgroundTasks):
    """API endpoint to ingest raw text, notes, or syllabus JSON (supports synchronous and asynchronous modes)."""
    try:
        clean_title = payload.title.strip()
        detected_subject = MaterialParser.detect_subject(clean_title, payload.raw_text, fallback=payload.subject or "General")
        effective_subject = detected_subject or payload.subject or "General"

        existing = CourseManager.find_course_by_title(clean_title)
        if existing and not existing.get("is_builtin", False):
            course_id = existing["course_id"]
        else:
            course_id = f"custom_{effective_subject.lower()[:3]}_{uuid.uuid4().hex[:6]}"

        if payload.async_mode:
            job_id = f"job_{uuid.uuid4().hex[:8]}"
            INGESTION_JOBS[job_id] = {
                "job_id": job_id,
                "course_id": course_id,
                "title": clean_title,
                "subject": effective_subject,
                "status": "queued",
                "progress": 0,
                "error": None
            }
            background_tasks.add_task(
                _async_ingest_worker,
                job_id=job_id,
                title=clean_title,
                subject=effective_subject,
                academic_tier=payload.academic_tier,
                raw_text=payload.raw_text,
                course_id=course_id,
                enrich_count=payload.enrich_count,
                enrich_chapters=payload.enrich_chapters,
                include_cards=payload.include_cards,
                resume=payload.resume
            )
            return {
                "status": "processing",
                "message": f"Async ingestion started for '{clean_title}'.",
                "job_id": job_id,
                "course_id": course_id
            }

        course = process_and_ingest_material(
            title=payload.title,
            subject=effective_subject,
            academic_tier=payload.academic_tier,
            raw_text=payload.raw_text,
            course_id=course_id,
            enrich_count=payload.enrich_count,
            enrich_chapters=payload.enrich_chapters,
            include_cards=payload.include_cards,
            resume=payload.resume
        )
        return {
            "status": "success",
            "message": f"Successfully ingested material and created course '{course['title']}'.",
            "course": course
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"Ingestion error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to ingest material: {str(e)}")

@app.post("/api/material/upload")
async def upload_material_file(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    subject: Optional[str] = Form("General"),
    academic_tier: Optional[str] = Form("Standard"),
    async_mode: Optional[bool] = Form(False),
    enrich_count: Optional[int] = Form(None),
    enrich_chapters: Optional[str] = Form(None),
    include_cards: Optional[bool] = Form(True),
    resume: Optional[bool] = Form(False),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """API endpoint to upload PDF, TXT, or Markdown documents.

    `enrich_count`/`enrich_chapters` let the learner cap the Llama phase
    (e.g. 10 out of 41 chapters); everything else is published immediately with
    the grounded deterministic skeleton and re-published as chapters land.
    """
    try:
        contents = await file.read()
        filename = (file.filename or "uploaded_document").lower()
        clean_title = title.strip() if (title and title.strip()) else os.path.splitext(file.filename or "Uploaded Material")[0]

        extracted_book = None
        if filename.endswith(".pdf") or contents.startswith(b"%PDF"):
            try:
                from book_extract import extract_pdf
                extracted_book = extract_pdf(contents)
                extracted_text = extracted_book.text
            except Exception as e:
                print(f"[Upload] extract_pdf failed: {e}. Falling back to bytes extraction.")
                extracted_text = MaterialParser.extract_text_from_document_bytes(contents, filename=file.filename or "")
        elif filename.endswith((".epub", ".mobi", ".xps", ".fb2")):
            extracted_text = MaterialParser.extract_text_from_document_bytes(contents, filename=file.filename or "")
        else:
            extracted_text = contents.decode("utf-8", errors="replace")

        detected_subject = MaterialParser.detect_subject(clean_title, extracted_text, fallback=subject or "General")
        effective_subject = detected_subject or subject or "General"

        existing = CourseManager.find_course_by_title(clean_title)
        if existing and not existing.get("is_builtin", False):
            course_id = existing["course_id"]
        else:
            course_id = f"custom_{effective_subject.lower()[:3]}_{uuid.uuid4().hex[:6]}"

        if async_mode:
            job_id = f"job_{uuid.uuid4().hex[:8]}"
            INGESTION_JOBS[job_id] = {
                "job_id": job_id,
                "course_id": course_id,
                "title": clean_title,
                "subject": effective_subject,
                "status": "queued",
                "progress": 0,
                "error": None
            }
            background_tasks.add_task(
                _async_ingest_worker,
                job_id=job_id,
                title=clean_title,
                subject=effective_subject,
                academic_tier=academic_tier or "Standard",
                raw_text=extracted_text,
                course_id=course_id,
                enrich_count=enrich_count,
                enrich_chapters=enrich_chapters,
                include_cards=include_cards if include_cards is not None else True,
                resume=resume if resume is not None else False,
                extracted_book=extracted_book
            )
            return {
                "status": "processing",
                "message": f"Async ingestion job queued for '{file.filename}'.",
                "job_id": job_id,
                "course_id": course_id
            }
            
        course = process_and_ingest_material(
            title=clean_title,
            subject=subject or "General",
            academic_tier=academic_tier or "Standard",
            raw_text=extracted_text,
            course_id=course_id,
            enrich_count=enrich_count,
            enrich_chapters=enrich_chapters,
            include_cards=include_cards if include_cards is not None else True,
            resume=resume if resume is not None else False,
            extracted_book=extracted_book
        )
        return {
            "status": "success",
            "message": f"Successfully parsed '{file.filename}' into course '{course['title']}'.",
            "course": course
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"File upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process uploaded file: {str(e)}")


def _async_enrich_worker(job_id: str, course_id: str,
                         enrich_count: Optional[int] = None,
                         enrich_chapters: Optional[str] = None,
                         include_cards: bool = True,
                         resume: bool = True):
    """Enriches more chapters of an existing course, re-publishing each one."""
    try:
        qge = QuestionGeneratorEngine()
        course = CourseManager.get_course_by_id(course_id)
        if not course:
            raise HTTPException(status_code=404, detail="Course not found.")
        chapters = course.get("chapters", [])
        if not chapters:
            raise ValueError("Course has no chapters to enrich.")

        spec = enrich_chapters if enrich_chapters is not None else enrich_count
        llm_targets = _select_chapters_for_llm(chapters, spec)
        if resume:
            llm_targets = {n for n in llm_targets
                           if n not in {c.get("chapter_index") for c in chapters
                                        if c.get("theory_source") == "llm"}}
        already_enriched = sum(1 for c in chapters
                               if c.get("theory_source") == "llm")
        planned = len(llm_targets)
        if not planned:
            if job_id in INGESTION_JOBS:
                INGESTION_JOBS[job_id]["status"] = "completed"
                INGESTION_JOBS[job_id]["current_message"] = "Nothing left to enrich."
                INGESTION_JOBS[job_id]["progress"] = 100
            return

        est = estimate_llm_build(planned)
        if job_id in INGESTION_JOBS:
            INGESTION_JOBS[job_id]["total_chapters"] = len(chapters)
            INGESTION_JOBS[job_id]["chapters_planned"] = planned
            INGESTION_JOBS[job_id]["chapters_total"] = len(chapters)
            INGESTION_JOBS[job_id]["chapters_enriched"] = already_enriched
            INGESTION_JOBS[job_id]["current_message"] = (
                f"Enriching {planned} more chapter(s) (~{est['minutes']} min)...")
            INGESTION_JOBS[job_id]["progress"] = 15

        all_cards = [c for chh in chapters for c in chh.get("cards", [])]
        avg_seconds = None
        done = 0
        coverage = {}
        subject = course.get("subject", "General")
        tier = course.get("academic_tier", "Undergraduate")

        for ch in chapters:
            num = ch.get("chapter_index")
            if num not in llm_targets:
                continue
            started = time.time()
            theory = qge.generate_chapter_theory_and_cards(
                chapter_title=ch.get("title", f"Chapter {num}"),
                chapter_text=ch.get("full_text", "")[:9000],
                subject=subject,
                tier=tier,
                chapter_index=num,
                use_llm=True,
                include_cards=include_cards,
                allow_cloud_fallback=False,
            )
            ch["summary"] = theory.get("summary", "")
            ch["objectives"] = theory.get("objectives", [])
            ch["cards"] = theory.get("cards", [])
            ch["deep_theory"] = theory.get("deep_theory", {})
            ch["theory_source"] = theory.get("theory_source", "deterministic")
            all_cards = [c for chh in chapters for c in chh.get("cards", [])]

            done += 1
            elapsed = time.time() - started
            avg_seconds = (elapsed if avg_seconds is None
                           else (avg_seconds * (done - 1) + elapsed) / done)
            remaining = max(0, planned - done)
            eta_sec = int(remaining * avg_seconds) if avg_seconds else None

            course["chapters"] = chapters
            course["cards"] = all_cards
            course["flashcards_count"] = len(all_cards)
            coverage = _theory_coverage(chapters)
            course["theory_coverage"] = coverage
            _persist_course(course)

            if job_id in INGESTION_JOBS:
                INGESTION_JOBS[job_id]["chapters_enriched"] = already_enriched + done
                INGESTION_JOBS[job_id]["eta_seconds"] = eta_sec
                INGESTION_JOBS[job_id]["avg_seconds_per_chapter"] = (
                    round(avg_seconds, 1) if avg_seconds else None)
                INGESTION_JOBS[job_id]["current_message"] = (
                    f"Enriched chapter {num} [{done}/{planned}]"
                    + (f" | ~{round(eta_sec / 60, 1)} min left" if eta_sec else ""))
                INGESTION_JOBS[job_id]["progress"] = int(15 + (done / max(1, planned)) * 80)
            print(f"[Enrich] planned {planned} -> done {done}: chapter {num} ({course_id})")

        if job_id in INGESTION_JOBS:
            INGESTION_JOBS[job_id]["status"] = "completed"
            INGESTION_JOBS[job_id]["current_step"] = 5
            INGESTION_JOBS[job_id]["current_message"] = (
                f"Enrichment complete — {coverage['enriched_count']}/"
                f"{coverage['chapters_total']} chapters now have Llama theory.")
            INGESTION_JOBS[job_id]["progress"] = 100
            INGESTION_JOBS[job_id]["chapters_enriched"] = coverage["enriched_count"]
            INGESTION_JOBS[job_id]["chapters_total"] = coverage["chapters_total"]
            INGESTION_JOBS[job_id]["eta_seconds"] = 0
            INGESTION_JOBS[job_id]["course"] = course
    except Exception as e:
        print(f"[Async Enrich Worker] Error enriching {course_id}: {e}")
        if job_id in INGESTION_JOBS:
            INGESTION_JOBS[job_id]["status"] = "failed"
            INGESTION_JOBS[job_id]["error"] = str(e)

@app.post("/api/material/course/{course_id}/enrich")
async def enrich_more_chapters(course_id: str, payload: EnrichCoursePayload,
                               background_tasks: BackgroundTasks):
    """Continue a partial build: enrich more chapters in the background.

    Always resumes (never redoes `theory_source == "llm"` chapters) and
    re-publishes the course as each enriched chapter lands, so the learner can
    watch a 10/41 course become 20/41 live. Poll /api/material/job/{id}/status.
    """
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    INGESTION_JOBS[job_id] = {
        "job_id": job_id,
        "course_id": course_id,
        "status": "queued",
        "progress": 0,
        "error": None,
    }
    background_tasks.add_task(
        _async_enrich_worker,
        job_id=job_id,
        course_id=course_id,
        enrich_count=payload.enrich_count,
        enrich_chapters=payload.enrich_chapters,
        include_cards=payload.include_cards,
        resume=payload.resume,
    )
    return {"status": "processing",
            "message": f"Enrichment queued for course '{course_id}'.",
            "job_id": job_id, "course_id": course_id}


@app.get("/api/material/job/{job_id}/status")
async def get_ingestion_job_status(job_id: str):
    """Polls real-time progress for async ingestion background jobs."""
    if job_id not in INGESTION_JOBS:
        raise HTTPException(status_code=404, detail="Ingestion job not found.")
    return INGESTION_JOBS[job_id]

@app.get("/api/material/courses")
async def get_all_courses():
    """Lists all available standard and ingested custom courses."""
    return {"courses": CourseManager.list_all_courses()}

@app.get("/api/material/course/{course_id}")
async def get_course_detail(course_id: str):
    """Retrieves full course structure and theory chapters for a specific course ID."""
    course = CourseManager.get_course_by_id(course_id)
    if not course:
        # Check if this course is currently processing in background
        for j in INGESTION_JOBS.values():
            if j.get("course_id") == course_id and j.get("status") in ["queued", "processing"]:
                return {
                    "course_id": course_id,
                    "title": j.get("title"),
                    "status": "processing",
                    "progress": j.get("progress", 0),
                    "chapters": []
                }
        raise HTTPException(status_code=404, detail=f"Course '{course_id}' not found.")
    return course

@app.delete("/api/material/course/{course_id}")
async def delete_custom_course(course_id: str):
    """Deletes a custom user course and cleans vector embeddings."""
    success = CourseManager.delete_custom_course(course_id)
    if not success:
        raise HTTPException(status_code=404, detail="Course not found or is a protected built-in course.")
    
    # Clean up associated vector embeddings to keep ChromaDB storage lean
    try:
        db_pipe = DatabaseIngestPipeline()
        db_pipe.delete_course_vectors(course_id)
    except Exception as e:
        print(f"[Course Cleanup] Warning deleting vector chunks: {e}")

    return {"status": "success", "message": f"Course '{course_id}' and associated vector embeddings deleted."}


# --- BACKEND ENDPOINT ROUTERS ---

@app.post("/api/tutor/load-theory")
async def load_dynamic_theory(payload: TheoryRequestPayload):
    # If a custom course_id is specified, load directly from CourseManager
    if payload.course_id:
        course = CourseManager.get_course_by_id(payload.course_id)
        if course:
            return {
                "course_id": course.get("course_id"),
                "title": course.get("title"),
                "subject": course.get("subject"),
                "academic_tier": course.get("academic_tier"),
                "chapters": course.get("chapters", []),
                "cards": course.get("cards", []),
                "quizzes": course.get("quizzes", []),
                "finalExam": course.get("finalExam", []),
                "is_ai_generated": True,
                "is_cached": True,
                "is_custom": not course.get("is_builtin", False)
            }

    subject_repo = FLASHCARD_REPOSITORY.get(payload.current_subject, {})
    tier_data = subject_repo.get(payload.current_tier, {"cards": [], "quizzes": [], "finalExam": []})
    
    # Check if AI cards are already cached for this subject/tier
    cache_key = (payload.current_subject, payload.current_tier)
    if cache_key in _gemini_flashcard_cache:
        cards = _gemini_flashcard_cache[cache_key]
        is_ai = True
    else:
        cards = tier_data.get("cards", [])[:3]
        is_ai = False

    # Derive logical chapters for built-in courses
    chapters = []
    for idx, c in enumerate(cards, 1):
        chapters.append({
            "chapter_id": f"ch_{idx}",
            "chapter_index": idx,
            "title": c.get("topic", f"Chapter {idx}"),
            "summary": c.get("answer", ""),
            "objectives": [c.get("question", "")],
            "cards": [c]
        })

    return {
        "cards": cards,
        "chapters": chapters,
        "quizzes": tier_data.get("quizzes", []),
        "finalExam": tier_data.get("finalExam", []),
        "is_ai_generated": is_ai,
        "is_cached": cache_key in _gemini_flashcard_cache,
        "is_custom": False
    }


@app.post("/api/tutor/generate-flashcards")
async def generate_ai_flashcards(payload: TheoryRequestPayload):
    """
    Triggers explicit Gemini RAG flashcard generation (max 3 cards) from ChromaDB chunks.
    Uses in-memory caching to minimize LLM token cost.
    """
    result = generate_gemini_flashcards_from_chroma(payload.current_subject, payload.current_tier)
    return result

@app.post("/api/tutor/chat")
async def run_session_cycle(payload: ChatSessionPayload):
    """
    Adaptive Interactive Discussion & Inquiry Tutor Agent.
    Evaluates query depth and routes dynamically to Surface, Deep, or Remedial discussion nodes.
    """
    messages_history = []
    for chat in payload.history[-6:]:
        if chat.get("sender") in ["user", "student"]:
            messages_history.append(HumanMessage(content=chat["text"]))
        else:
            messages_history.append(AIMessage(content=chat["text"]))

    # Append current message turn
    messages_history.append(HumanMessage(content=payload.message))

    initial_graph_state = {
        "messages": messages_history,
        "time_taken_seconds": payload.time_taken,
        "consecutive_errors": payload.consecutive_errors,
        "requires_remedial_routing": False,
        "depth_level": "surface",
        "retrieved_curriculum": [],
        "active_agent_node": "Initialization",
        "subject": payload.current_subject,
        "academic_tier": payload.current_tier,
        "course_id": payload.course_id or "",
        "chapter_id": payload.chapter_id or "",
        "current_question": payload.current_question,
        "inquiry_type": payload.inquiry_type
    }

    try:
        final_graph_state = compiled_tutor_app.invoke(initial_graph_state)
        response_text = final_graph_state["messages"][-1].content
        active_node = final_graph_state.get("active_agent_node", "Discussion Node")
        depth_level = final_graph_state.get("depth_level", "surface")
        remedial = final_graph_state.get("requires_remedial_routing", False)
        context = final_graph_state.get("retrieved_curriculum", [])
        mamdani_eval = {
            "fuzzy_score": final_graph_state.get("fuzzy_score", 70.0),
            "performance_tier": final_graph_state.get("performance_tier", "Developing"),
            "linguistic_remark": final_graph_state.get("linguistic_remark", ""),
            "degree_of_failure": final_graph_state.get("degree_of_failure", 30.0)
        }
    except Exception as e:
        print(f"Error in tutor chat execution: {e}")
        response_text = f"I see you're exploring **{payload.message}**. Let me guide you through the core {payload.current_subject} principles!"
        active_node = "Discussion Node"
        depth_level = "surface"
        remedial = False
        context = []
        mamdani_eval = {
            "fuzzy_score": 60.0,
            "performance_tier": "Developing",
            "linguistic_remark": "Developing Trajectory",
            "degree_of_failure": 40.0
        }

    return {
        "response": response_text,
        "active_node": active_node,
        "depth_level": depth_level,
        "remedial_triggered": remedial,
        "context_pulled": context,
        "mamdani_evaluation": mamdani_eval
    }

@app.post("/api/tutor/evaluate-short-answer")
async def evaluate_short_answer(payload: ShortAnswerPayload):
    """
    3-Stage Pipeline for Multi-Parameter Mamdani-driven adaptive hint generation.
    """
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    model = None
    if api_key:
        try:
            model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.2, google_api_key=api_key)
        except Exception as e:
            print("GEMINI INIT NOTICE:", e)

    # ══════════════════════════════════════════════════════════════════════════════
    # STAGE 1 — Combined Grading + Error Severity + Specific Gap Diagnosis
    # ══════════════════════════════════════════════════════════════════════════════
    diagnostic_prompt = (
        "You are a precise academic grading diagnostic engine.\n\n"
        f"SUBJECT: {payload.current_subject} | LEVEL: {payload.current_tier}\n"
        f"QUESTION: {payload.question_text}\n"
        f"EXPECTED ANSWER: {payload.expected_answer}\n"
        f"STUDENT SUBMITTED: {payload.student_raw_input}\n\n"
        "Your job is THREE things:\n"
        "  A) Score the student's answer with partial credit (accept unit variants, rounding ±5%, whitespace, case differences).\n"
        "  B) Estimate error_severity from 0.0 to 1.0:\n"
        "     - 0.0 to 0.2: Minor typo, sign swap, or rounding approximation.\n"
        "     - 0.3 to 0.6: Procedural/algebraic error, wrong intermediate step, or related distractor.\n"
        "     - 0.7 to 1.0: Complete conceptual misunderstanding, invalid formula, or unrelated answer.\n"
        "  C) Write a 1-2 sentence gap_analysis that describes the SPECIFIC error in the student's\n"
        "     submission. Be precise: name the wrong value, missing concept, incorrect unit, wrong sign,\n"
        "     or missing step. Do NOT be generic ('the answer is wrong'). Reference the student's actual words.\n"
        "     CRITICAL: Never reveal the correct answer, expected value, or final numerical result.\n\n"
        "Respond ONLY with a minified JSON object — no markdown, no explanation:\n"
        '{"accuracy_percentage": <float 0.0-100.0>, "is_logically_correct": <true|false>, '
        '"error_severity": <float 0.0-1.0>, '
        '"gap_analysis": "<1-2 sentence diagnosis of the exact error in the student\'s answer>"}'
    )
    gap_analysis = "No specific error analysis available."
    error_severity = 0.0
    try:
        diag_res_text = None
        if model:
            try:
                diag_res = model.invoke([HumanMessage(content=diagnostic_prompt)])
                diag_res_text = diag_res.content
            except Exception as ge:
                print(f"[evaluate_short_answer] Gemini diagnostic warning: {ge}")

        if not diag_res_text and local_llm.is_available():
            try:
                diag_res_text = local_llm.generate(prompt=diagnostic_prompt, system_prompt="You are a JSON-only grading diagnostic engine.")
            except Exception as le:
                print(f"[evaluate_short_answer] Local LLM diagnostic warning: {le}")

        if not diag_res_text:
            raise ValueError("Offline mode: running local deterministic diagnostic engine.")

        clean_json = local_llm._clean_json_str(diag_res_text)
        diag_data  = json.loads(clean_json)
        base_accuracy = float(diag_data.get("accuracy_percentage", 0.0))
        is_correct    = bool(diag_data.get("is_logically_correct", False))
        if is_correct:
            base_accuracy = max(base_accuracy, 95.0)
            error_severity = 0.0
        else:
            error_severity = float(diag_data.get("error_severity", 0.7))
        gap_analysis  = sanitize_gap_analysis(
            str(diag_data.get("gap_analysis", gap_analysis)).strip(),
            payload.expected_answer,
        )
    except Exception as e:
        print("DIAGNOSTIC ENGINE LOG/FALLBACK:", e)
        # Normalize student raw input and expected answer for math & text comparisons
        norm_student = payload.student_raw_input.strip().lower().replace(" ", "").replace("x=", "").replace("ans=", "").replace("answer=", "")
        norm_expected = payload.expected_answer.strip().lower().replace(" ", "").replace("x=", "")
        
        sim = compute_semantic_similarity(payload.student_raw_input, payload.expected_answer)
        is_correct = (norm_student == norm_expected) or (sim >= 0.70)
        
        if is_correct:
            base_accuracy = max(92.0, round(sim * 100.0, 1))
            error_severity = max(0.0, round((1.0 - sim) * 0.4, 2))
            gap_analysis = "Submission matches or semantically captures the required concept."
        elif sim >= 0.40:
            base_accuracy = round(sim * 75.0, 1)
            error_severity = min(0.65, max(0.3, round(1.0 - sim, 2)))
            gap_analysis = sanitize_gap_analysis(
                f"The response '{payload.student_raw_input}' is partially aligned but missing core terms or exact derivation.",
                payload.expected_answer
            )
        else:
            base_accuracy = round(sim * 50.0, 1)
            error_severity = min(1.0, max(0.6, round(1.0 - sim, 2)))
            gap_analysis = sanitize_gap_analysis(
                f"The student wrote '{payload.student_raw_input}', but the result "
                f"does not satisfy the required theoretical relationship. Review the governing relationship.",
                payload.expected_answer,
            )

    # ══════════════════════════════════════════════════════════════════════════════
    # STAGE 2 — Multi-Parameter Mamdani Fuzzy Inference
    # ══════════════════════════════════════════════════════════════════════════════
    evaluation = FuzzyMarkingSystem.evaluate_performance(
        accuracy_pct=base_accuracy,
        latency_seconds=payload.seconds_spent,
        attempts_count=payload.attempts_count,
        error_severity=error_severity,
        hints_requested=getattr(payload, "hints_requested", 0)
    )
    fuzzy_score       = evaluation["fuzzy_score"]
    defuzzified_score = evaluation.get("defuzzified_score", fuzzy_score)
    performance_tier  = evaluation["performance_tier"]
    linguistic_remark = evaluation["linguistic_remark"]
    degree_of_failure = evaluation["degree_of_failure"]

    # ══════════════════════════════════════════════════════════════════════════════
    # STAGE 3 — Mamdani-Calibrated 3-Level Progressive Hint Ladder
    # ══════════════════════════════════════════════════════════════════════════════
    hint_response = ""
    if not is_correct:
        hint_lvl = getattr(payload, "hint_level", 1)
        shared_context = (
            f"SUBJECT: {payload.current_subject} | LEVEL: {payload.current_tier}\n"
            f"QUESTION: {payload.question_text}\n"
            f"STUDENT'S ANSWER: {payload.student_raw_input}\n"
            f"REQUESTED HINT LEVEL: Level {hint_lvl} (1=Socratic, 2=Formula Reminder, 3=Worked Setup)\n\n"
            f"MAMDANI FUZZY SYSTEM DIAGNOSIS:\n"
            f"  Performance Tier   : {performance_tier}\n"
            f"  Fuzzy Score        : {fuzzy_score}%\n"
            f"  Degree of Failure  : {degree_of_failure}%\n"
            f"  Error Severity     : {error_severity:.2f} (0=minor slip, 1=critical flaw)\n"
            f"  Linguistic Verdict : {linguistic_remark}\n\n"
            f"SPECIFIC ERROR IN STUDENT'S ANSWER (from diagnostic engine):\n"
            f"  {gap_analysis}\n\n"
            f"GOVERNING FORMULA / KEY CONCEPT (internal reference — do NOT reveal final result):\n"
            f"  {payload.hint_formula or 'derive from question parameters'}\n\n"
        )

        if hint_lvl == 1:
            level_directive = (
                "HINT LEVEL 1 (SOCRATIC NUDGE):\n"
                "1. In ONE sentence, point out what physical or conceptual relationship the student considered.\n"
                "2. Ask ONE guiding Socratic question that prompts them to identify the missing or misapplied condition.\n"
                "3. Strictly do NOT name the formula or state any numbers."
            )
        elif hint_lvl == 2:
            level_directive = (
                "HINT LEVEL 2 (FORMULA & PRINCIPLE REMINDER):\n"
                f"1. Explicitly name the governing formula or principle ({payload.hint_formula or 'core law'}).\n"
                "2. Describe what each symbol represents in this problem's context.\n"
                "3. Do NOT substitute numerical values or calculate the result."
            )
        else:
            level_directive = (
                "HINT LEVEL 3 (WORKED INTERMEDIATE SETUP):\n"
                "1. State the formula and show the substitution of the given parameters into the equation.\n"
                "2. Stop right before the final algebraic/arithmetic step.\n"
                "3. Prompt the student to carry out the final calculation step themselves.\n"
                "4. Strictly NEVER state the final numerical answer."
            )

        hint_prompt = (
            "You are an adaptive Socratic academic tutor.\n\n"
            + shared_context +
            f"KNOWN MISCONCEPTION PATTERN: {payload.hint_misconception or 'general conceptual gap'}\n\n"
            f"{level_directive}\n"
            "Do NOT be generic. Every sentence must address THIS student's specific submission."
            + HINT_FORMAT_DIRECTIVE
        )

        hint_raw_text = None
        if model:
            try:
                response = model.invoke([HumanMessage(content=hint_prompt)])
                hint_raw_text = response.content
            except Exception as ge:
                print(f"[evaluate_short_answer] Gemini hint warning: {ge}")

        if not hint_raw_text and local_llm.is_available():
            try:
                hint_raw_text = local_llm.generate(prompt=hint_prompt, system_prompt="You are an adaptive Socratic academic tutor.")
            except Exception as le:
                print(f"[evaluate_short_answer] Local LLM hint warning: {le}")

        if hint_raw_text:
            hint_response = sanitize_hint_text(hint_raw_text, payload.expected_answer)
        else:
            if hint_lvl == 1:
                hint_response = sanitize_hint_text(
                    "## Socratic Nudge\n"
                    "- What physical relationship or principle connects the quantities given in this problem?\n"
                    f"- **Common pitfall:** {payload.hint_misconception or 'Carefully check the units and initial conditions.'}\n"
                    "- What is the primary state variable that governs this behavior?",
                    payload.expected_answer,
                )
            elif hint_lvl == 2:
                hint_response = sanitize_hint_text(
                    "## Formula & Principle Reminder\n"
                    f"- **Governing Concept:** {payload.hint_formula or 'Recall the governing equation for this topic.'}\n"
                    "- Identify all known parameters given in the problem statement.\n"
                    "- How can you rearrange this formula to isolate the target unknown?",
                    payload.expected_answer,
                )
            else:
                hint_response = sanitize_hint_text(
                    "## Worked Intermediate Setup\n"
                    f"- **Focus:** {gap_analysis}\n"
                    f"- **Governing Model:** {payload.hint_formula or 'Standard operational relation'}\n"
                    "- **Next Step:** Substitute your known numerical values into the equation and carry out the final calculation yourself.",
                    payload.expected_answer,
                )
    else:
        hint_response = (
            f"Correct! {linguistic_remark} "
            f"Fuzzy Mastery Score: {fuzzy_score}% — {performance_tier}."
        )

    # Post-generation pedagogical guardrail: ensure no calculus/Class 12 terms leak into Class 9 hints
    hint_response = filter_for_grade_level(hint_response, payload.current_tier)

    try:
        from analytics_db import AnalyticsDatabase
        AnalyticsDatabase.record_attempt(
            student_id=getattr(payload, "student_id", "default_student") or "default_student",
            course_id=payload.course_id or "",
            chapter_id=getattr(payload, "chapter_id", "ch_1") or "ch_1",
            question_id=payload.question_text[:40],
            question_type="short_answer",
            is_correct=is_correct,
            accuracy_pct=base_accuracy,
            fuzzy_score=fuzzy_score,
            error_severity=error_severity,
            hint_level=getattr(payload, "hint_level", 1),
            latency_seconds=float(payload.seconds_spent)
        )
    except Exception as ae:
        print(f"[Analytics] Attempt recording warning: {ae}")

    return {
        "is_correct":        is_correct,
        "fuzzy_score":       fuzzy_score,
        "defuzzified_score": defuzzified_score,
        "degree_of_failure": degree_of_failure,
        "performance_tier":  performance_tier,
        "linguistic_remark": linguistic_remark,
        "gap_analysis":      gap_analysis,
        "error_severity":    error_severity,
        "assigned_hint":     hint_response
    }


@app.post("/api/tutor/evaluate-exam")
async def evaluate_final_exam(payload: ExamSubmissionPayload):
    if payload.question_details:
        total_qs = len(payload.question_details)
        correct_qs = sum(1 for q in payload.question_details if q.get("is_correct", False))
        accuracy = sum(q.get("fuzzy_score", 0.0) for q in payload.question_details) / max(1, total_qs)
        total_time = sum(q.get("latency_seconds", 0) for q in payload.question_details)
        average_latency = total_time / max(1, total_qs)
        avg_attempts = sum(q.get("attempts", 1) for q in payload.question_details) / max(1, total_qs)
        avg_severity = sum(q.get("error_severity", 0.0) for q in payload.question_details) / max(1, total_qs)
    else:
        total_qs = max(1, payload.total_questions)
        correct_qs = payload.correct_answers
        accuracy = (correct_qs / total_qs) * 100
        average_latency = payload.total_elapsed_time / total_qs
        avg_attempts = 1.0
        avg_severity = 0.0 if accuracy >= 80.0 else 0.6

    assessment = FuzzyMarkingSystem.evaluate_performance(
        accuracy_pct=accuracy,
        latency_seconds=int(average_latency),
        attempts_count=int(round(avg_attempts)),
        error_severity=avg_severity
    )
    analytics = PathPerformanceAnalytics.calculate_pathway_improvement(
        mock_history=payload.mock_chat_history,
        exam_score=assessment["fuzzy_score"],
        exam_latency=average_latency
    )

    # ══════════════════════════════════════════════════════════════════════════════
    # RESOLVE QUESTION DETAILS & CONSTRUCT PERFORMANCE PROFILE
    # ══════════════════════════════════════════════════════════════════════════════
    subject_repo = FLASHCARD_REPOSITORY.get(payload.current_subject, {})
    tier_data = subject_repo.get(payload.current_tier, {"finalExam": []})
    exam_questions = {q["qId"]: q for q in tier_data.get("finalExam", [])}

    # Also resolve custom course questions if course_id is present
    if payload.course_id:
        custom_course = CourseManager.get_course_by_id(payload.course_id)
        if custom_course and custom_course.get("finalExam"):
            for q in custom_course.get("finalExam", []):
                exam_questions[q["qId"]] = q

    correct_details = []
    incorrect_details = []
    
    if payload.question_details:
        for q_detail in payload.question_details:
            q_id = q_detail.get("qId")
            is_corr = q_detail.get("is_correct", False)
            attempts = q_detail.get("attempts", 1)
            latency = q_detail.get("latency_seconds", 0)
            q_fuzzy_score = q_detail.get("fuzzy_score", 0.0)
            
            repo_q = exam_questions.get(q_id, {})
            topic = repo_q.get("moduleOrigin") or q_detail.get("moduleOrigin") or q_detail.get("topic") or "Core Topic"
            q_text = repo_q.get("text") or q_detail.get("text") or q_detail.get("question") or "Exam Problem"
            formula = repo_q.get("formula") or q_detail.get("formula") or ""
            misconception = repo_q.get("misconception") or q_detail.get("misconception") or ""
            
            info = {
                "qId": q_id,
                "topic": topic,
                "question": q_text,
                "formula": formula,
                "misconception": misconception,
                "attempts": attempts,
                "latency": latency,
                "fuzzy_score": q_fuzzy_score
            }
            if is_corr:
                correct_details.append(info)
            else:
                incorrect_details.append(info)

    # ══════════════════════════════════════════════════════════════════════════════
    # MAMDANI-CALIBRATED EXAM EVALUATION STUDY HINT GENERATION
    # ══════════════════════════════════════════════════════════════════════════════
    rating_tier = assessment["performance_tier"]
    calculated_score = assessment["fuzzy_score"]
    
    correct_desc = ""
    for idx, q in enumerate(correct_details, 1):
        correct_desc += f"  {idx}. Topic: {q['topic']} | Question: {q['question']} (Fuzzy Score: {q['fuzzy_score']}%, Latency: {q['latency']}s, Attempts: {q['attempts']})\n"
        
    incorrect_desc = ""
    for idx, q in enumerate(incorrect_details, 1):
        incorrect_desc += f"  {idx}. Topic: {q['topic']} | Question: {q['question']}\n"
        if q['formula']:
            incorrect_desc += f"     - Governing Formula: {q['formula']}\n"
        if q['misconception']:
            incorrect_desc += f"     - Common Misconception: {q['misconception']}\n"
        incorrect_desc += f"     - (Fuzzy Score: {q['fuzzy_score']}%, Latency: {q['latency']}s, Attempts: {q['attempts']})\n"

    prompt_context = (
        f"SUBJECT: {payload.current_subject} | LEVEL: {payload.current_tier}\n"
        f"OVERALL PERFORMANCE METRICS (Mamdani Fuzzy Inference System):\n"
        f"  - Fuzzy Evaluation Score: {calculated_score}%\n"
        f"  - Performance Rating Tier: {rating_tier}\n"
        f"  - Average Pacing Latency: {average_latency:.1f} seconds per question\n\n"
    )
    if correct_desc:
        prompt_context += f"TOPICS MASTERED / CORRECT ANSWERS:\n{correct_desc}\n"
    if incorrect_desc:
        prompt_context += f"TOPICS REQUIRING ATTENTION / INCORRECT ANSWERS:\n{incorrect_desc}\n"

    # Select level of hint based on performance tier
    if rating_tier == "High Mastery":
        level_instruction = (
            "Decided Hint Level: LEVEL 4 - ADVANCED CONCEPTUAL CHALLENGE (High Mastery)\n"
            "DIRECTIVE:\n"
            "1. Praise the student briefly and enthusiastically for their high mastery performance.\n"
            "2. Offer an advanced extension question or high-level conceptual challenge related to the course material "
            "   (e.g., if it is Class 10 Physics, present a challenging physics concept or scenario to think about).\n"
            "3. Provide brief guidance on how they would approach this advanced challenge."
        )
    elif rating_tier == "Moderate Mastery":
        level_instruction = (
            "Decided Hint Level: LEVEL 3 - EFFICIENCY & PRECISION CALIBRATION (Moderate Mastery)\n"
            "DIRECTIVE:\n"
            "1. Acknowledge their solid conceptual grasp (Moderate Mastery).\n"
            "2. Focus on efficiency, speed, or precision. Suggest specific pacing tips or minor calculations tricks.\n"
            "3. Give them one specific study hint on how to polish their execution (e.g. dimensional analysis, estimating answers, checking units) to reach the next tier."
        )
    elif rating_tier == "Developing":
        level_instruction = (
            "Decided Hint Level: LEVEL 2 - SOCRATIC STUDY HINT & GUIDANCE (Developing)\n"
            "DIRECTIVE:\n"
            "1. Reassure the student that they are on a developing trajectory and close to mastery.\n"
            "2. Do NOT give direct formulas or worked-out solutions for the missed questions.\n"
            "3. Pinpoint the conceptual gaps in the incorrect topics. Ask 1-2 Socratic questions that guide them to discover "
            "   the correct relationships or formulas for themselves during their review.\n"
            "4. Suggest a targeted area of study."
        )
    else:  # Intervention Required
        level_instruction = (
            "Decided Hint Level: LEVEL 1 - FOUNDATION REBUILD STUDY PLAN (Intervention Required)\n"
            "DIRECTIVE:\n"
            "1. Reassure the student and provide an encouraging, highly structured study path.\n"
            "2. Identify every failed topic clearly.\n"
            "3. Explain the core concepts for those topics WITHOUT giving worked solutions or final answers.\n"
            "4. Provide a structured review checklist with practice suggestions (concept review, not answer keys)."
        )

    hint_prompt = (
        "You are an expert academic tutor. You are analyzing a student's final exam performance details.\n"
        "Your task is to generate a custom 'Remediation Hint & Study Plan' for this student based on the Decided Hint Level.\n\n"
        + prompt_context +
        level_instruction + "\n\n"
        "FORMATTING REQUIREMENT:\n"
        "- Respond in clean, readable, professional markdown with ## headers and bullet lists.\n"
        "- Keep it concise, engaging, and highly personalized. Address the student directly as 'You'.\n"
        "- Do not use placeholders. Use actual subject names and topics from the context.\n"
        "- NEVER reveal final exam answers, exact numerical results, or completed substitutions."
    )

    remediation_hint = ""
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    def get_fallback_hint():
        if rating_tier == "High Mastery":
            return (
                f"Congratulations on your outstanding performance! You have achieved High Mastery with a score of {calculated_score}%.\n\n"
                f"**Level 4 Advanced Challenge:** Try applying these concepts to multi-body scenarios or deriving the governing equations from first principles."
            )
        elif rating_tier == "Moderate Mastery":
            return (
                f"Great job! You achieved Moderate Mastery with a score of {calculated_score}%.\n\n"
                f"**Level 3 Efficiency Calibration:** To refine your performance and reach the highest tier, focus on speed and pacing (average latency: {average_latency:.1f}s).\n"
                f"*Tip: Try dimensional analysis or estimation techniques to verify your steps quickly.*"
            )
        elif rating_tier == "Developing":
            topics_list = ", ".join(set(q["topic"] for q in incorrect_details)) if incorrect_details else "the missed topics"
            return (
                f"You are on a developing trajectory with a score of {calculated_score}%.\n\n"
                f"**Level 2 Socratic Guidance:** Review the following topics that you struggled with: {topics_list}.\n"
                f"*Socratic Study Tip: For each missed question, ask yourself what the physical quantities represent and how they vary in relation to each other.*"
            )
        else:
            remediation_steps = ""
            for idx, q in enumerate(incorrect_details, 1):
                remediation_steps += f"  - **{q['topic']}**: review the underlying concept and practice similar problems.\n"
            remediation_steps = remediation_steps or "  - Review core module concepts and practice untimed drills.\n"
            return (
                f"## Foundation Rebuild Plan\n"
                f"Targeted review recommended (Overall Score: {calculated_score}%).\n\n"
                f"### Topics to revisit\n"
                f"{remediation_steps}\n"
                f"### Study advice\n"
                f"- Re-read each topic's key relationships, then solve 3 practice problems without looking at solutions."
            )

    if api_key:
        try:
            model = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.2, google_api_key=api_key)
            response = model.invoke([HumanMessage(content=hint_prompt)])
            remediation_hint = response.content.strip()
            for q in incorrect_details:
                repo_q = exam_questions.get(q.get("qId", ""), {})
                expected = repo_q.get("expected", "")
                if expected:
                    remediation_hint = sanitize_hint_text(remediation_hint, expected)
        except Exception as e:
            print("GEMINI API ERROR IN EVALUATE-EXAM:", e)
            remediation_hint = get_fallback_hint()
    else:
        remediation_hint = get_fallback_hint()
    
    return {
        "subject": payload.current_subject,
        "grade_tier": payload.current_tier,
        "calculated_score": assessment["fuzzy_score"],
        "rating_tier": assessment["performance_tier"],
        "mentor_remark": assessment["linguistic_remark"],
        "remediation_hint": remediation_hint,
        "growth_metrics": analytics
    }


# ══════════════════════════════════════════════════════════════════════════════
# STREAMING TUTOR CHAT (SERVER-SENT EVENTS)
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/tutor/chat/stream")
async def run_session_cycle_stream(payload: ChatSessionPayload):
    """
    Server-Sent Events (SSE) streaming endpoint for the adaptive inquiry tutor.
    Streams tokens in real-time, reducing perceived response latency to ~1s.
    """
    async def sse_event_generator():
        messages_history = []
        for chat in payload.history[-6:]:
            if chat.get("sender") in ["user", "student"]:
                messages_history.append(HumanMessage(content=chat["text"]))
            else:
                messages_history.append(AIMessage(content=chat["text"]))

        messages_history.append(HumanMessage(content=payload.message))

        initial_graph_state = {
            "messages": messages_history,
            "time_taken_seconds": payload.time_taken,
            "consecutive_errors": payload.consecutive_errors,
            "requires_remedial_routing": False,
            "depth_level": "surface",
            "retrieved_curriculum": [],
            "active_agent_node": "Initialization",
            "subject": payload.current_subject,
            "academic_tier": payload.current_tier,
            "course_id": payload.course_id or "",
            "chapter_id": payload.chapter_id or "",
            "current_question": payload.current_question,
            "inquiry_type": payload.inquiry_type
        }

        try:
            final_response = ""
            active_node = "Discussion Node"
            for event in compiled_tutor_app.stream(initial_graph_state):
                for node_name, node_output in event.items():
                    active_node = node_output.get("active_agent_node", node_name)
                    if "messages" in node_output and node_output["messages"]:
                        last_m = node_output["messages"][-1]
                        content = getattr(last_m, "content", "")
                        if content and content != final_response:
                            delta = content[len(final_response):] if content.startswith(final_response) else content
                            final_response = content
                            yield f"data: {json.dumps({'token': delta, 'active_node': active_node})}\n\n"

            yield f"data: {json.dumps({'done': True, 'response': final_response, 'active_node': active_node})}\n\n"
        except Exception as e:
            fallback = f"Let's explore **{payload.message}**. What fundamental principles come to mind?"
            yield f"data: {json.dumps({'token': fallback, 'done': True, 'active_node': 'Fallback Node'})}\n\n"

    return StreamingResponse(sse_event_generator(), media_type="text/event-stream")


# ══════════════════════════════════════════════════════════════════════════════
# SPACED REPETITION (SM-2) ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/api/srs/review")
async def record_srs_card_review(payload: SRSReviewPayload):
    """Updates card review interval and repetitions using SuperMemo-2 (SM-2)."""
    result = SpacedRepetitionManager.record_review(
        student_id=payload.student_id,
        card_id=payload.card_id,
        quality=payload.quality,
        course_id=payload.course_id,
        chapter_id=payload.chapter_id,
        card_data=payload.card_data
    )
    return result

@app.get("/api/srs/due/{student_id}")
async def get_due_srs_cards(student_id: str, course_id: Optional[str] = None):
    """Retrieves all flashcards scheduled for review on or before today."""
    due = SpacedRepetitionManager.get_due_cards(student_id, course_id)
    return {"due_cards": due, "count": len(due)}

@app.get("/api/srs/stats/{student_id}")
async def get_student_srs_stats(student_id: str):
    """Calculates student retention stats, learning cards, and mature cards."""
    return SpacedRepetitionManager.get_student_stats(student_id)


# ══════════════════════════════════════════════════════════════════════════════
# PERSISTENT LEARNING ANALYTICS ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/api/analytics/heatmap/{student_id}/{course_id}")
async def get_student_course_heatmap(student_id: str, course_id: str):
    """Returns per-chapter mastery performance and attempts breakdown."""
    from analytics_db import AnalyticsDatabase
    heatmap = AnalyticsDatabase.get_course_mastery_heatmap(student_id, course_id)
    return {"student_id": student_id, "course_id": course_id, "heatmap": heatmap}

@app.get("/api/analytics/summary/{student_id}")
async def get_student_trajectory_summary(student_id: str):
    """Returns overall student learning trajectory, total attempts, and average accuracy."""
    from analytics_db import AnalyticsDatabase
    return AnalyticsDatabase.get_student_summary(student_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)