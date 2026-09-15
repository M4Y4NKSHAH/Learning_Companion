import os
import json
import uuid
from typing import Optional, List
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI

# Load the .env file automatically
load_dotenv()

from fuzzy_engine import FuzzyMarkingSystem
from analytics import PathPerformanceAnalytics
from theory_repo import FLASHCARD_REPOSITORY
from tutor_graph import compiled_tutor_app
from flashcard_builder import build_flashcards_from_chroma, generate_gemini_flashcards_from_chroma, _gemini_flashcard_cache
from hint_utils import sanitize_gap_analysis, sanitize_hint_text, HINT_FORMAT_DIRECTIVE
from material_parser import MaterialParser
from course_manager import CourseManager
from question_generator import QuestionGeneratorEngine
from database_ingest import DatabaseIngestPipeline

app = FastAPI(title="Unified Agentic Socratic Tutoring Platform")

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

class ChatSessionPayload(BaseModel):
    message: str
    time_taken: int
    consecutive_errors: int
    current_tier: str
    current_subject: str
    course_id: Optional[str] = None
    history: list[dict] = []
    current_question: dict = {}
    inquiry_type: str = "discussion"


class ShortAnswerPayload(BaseModel):
    question_text: str
    student_raw_input: str
    expected_answer: str
    seconds_spent: int
    attempts_count: int
    current_tier: str
    current_subject: str
    course_id: Optional[str] = None
    hint_formula: str = ""
    hint_misconception: str = ""
    hints_requested: int = 0

class ExamSubmissionPayload(BaseModel):
    correct_answers: int = 0
    total_questions: int = 0
    total_elapsed_time: int = 0
    current_tier: str
    current_subject: str
    course_id: Optional[str] = None
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
def process_and_ingest_material(
    title: str,
    subject: str,
    academic_tier: str,
    raw_text: str
) -> dict:
    """
    Enterprise Ingestion Pipeline:
    1. Sanitizes input material.
    2. Decomposes document into structured chapters/topics.
    3. Generates high-retention theory summaries and flashcards per chapter.
    4. Vectors chunks into ChromaDB with course/chapter namespaces.
    5. Synthesizes formative quizzes and summative final exam questions.
    6. Persists the complete course into local storage.
    """
    clean_text = MaterialParser.clean_text(raw_text)
    if len(clean_text) < 50:
        raise HTTPException(status_code=400, detail="The provided material is too short to extract a curriculum.")

    # 1. Detect / Decompose into chapters
    raw_chapters = MaterialParser.detect_outline_or_chapters(clean_text)
    if not raw_chapters:
        raw_chapters = [{
            "chapter_index": 1,
            "title": f"{title} - Core Fundamentals",
            "content": clean_text
        }]

    course_id = f"custom_{subject.lower()[:3]}_{uuid.uuid4().hex[:6]}"
    qge = QuestionGeneratorEngine()
    db_pipeline = DatabaseIngestPipeline()

    # 1. Single-Pass Guiding Agent Blueprint (Ultra-low token usage: ~350 tokens for entire course)
    raw_headings = [ch.get("title", "") for ch in raw_chapters]
    guided_blueprint = qge.generate_guided_curriculum_blueprint(
        course_title=title,
        material_sample=clean_text,
        subject=subject,
        tier=academic_tier,
        detected_headings=raw_headings
    )

    processed_chapters = []
    all_cards = []

    if guided_blueprint and len(guided_blueprint) > 0:
        print(f"[Ingestion] Applying guiding agent blueprint across {len(guided_blueprint)} chapters...")
        for idx, g_ch in enumerate(guided_blueprint, 1):
            ch_id = f"ch_{idx}"
            ch_title = g_ch.get("title", f"Chapter {idx}")
            ch_summary = g_ch.get("summary", "")
            ch_objs = g_ch.get("objectives", [])
            
            # Map raw content slice if available
            ch_content = raw_chapters[idx - 1].get("content", "") if idx - 1 < len(raw_chapters) else clean_text[:4000]
            
            # Format flashcards
            ch_cards = []
            for c_idx, c in enumerate(g_ch.get("cards", [])):
                ch_cards.append({
                    "id": f"c{idx}_{c_idx+1}_{uuid.uuid4().hex[:4]}",
                    "topic": c.get("topic", ch_title),
                    "question": c.get("question", f"Core principle in {ch_title}"),
                    "answer": c.get("answer", "• Governing theoretical axiom and mechanics.")
                })
            all_cards.extend(ch_cards)

            # Deep theory suite from guiding agent
            deep_theory = {
                "principles": g_ch.get("principles", [{"title": "Primary Law", "content": ch_summary, "tag": "Core Axiom"}]),
                "formulations": g_ch.get("formulations", [{"title": "Mathematical Model", "formula": f"Governing model for {ch_title}", "derivation": "Derived from foundational conservation laws.", "variables": "State properties and constants."}]),
                "mental_models": g_ch.get("mental_models", [{"concept": "Intuitive Model", "analogy": f"System dynamic representing {ch_title}.", "takeaway": "Focus on state invariants."}]),
                "applications": g_ch.get("applications", [{"domain": f"Applied {subject}", "description": f"Deploys theoretical principles of {ch_title}."}]),
                "misconceptions": g_ch.get("misconceptions", [{"trap": "Formula misapplication", "correction": "Verify operational assumptions prior to calculation."}])
            }

            # Vectorize chunks into ChromaDB with SHA-256 deduplication
            chunks = MaterialParser.create_semantic_chunks(ch_content[:8000], chunk_size=400, overlap=40)[:15]
            try:
                db_pipeline.ingest_custom_chunks(
                    course_id=course_id,
                    chunks=chunks,
                    subject=subject,
                    academic_tier=academic_tier,
                    chapter_id=ch_id,
                    chapter_index=idx
                )
            except Exception as ve:
                print(f"[ChromaDB] Vector ingestion warning: {ve}")

            processed_chapters.append({
                "chapter_id": ch_id,
                "chapter_index": idx,
                "title": ch_title,
                "summary": ch_summary,
                "objectives": ch_objs,
                "cards": ch_cards,
                "deep_theory": deep_theory,
                "full_text": ch_content,
                "content_preview": ch_content[:400] + "..." if len(ch_content) > 400 else ch_content
            })
    else:
        # Fallback: Local offline extraction
        if len(raw_chapters) > 8:
            raw_chapters = raw_chapters[:8]

        for ch in raw_chapters:
            ch_idx = ch.get("chapter_index", len(processed_chapters) + 1)
            ch_title = ch.get("title", f"Chapter {ch_idx}")
            ch_content = ch.get("content", "")
            ch_id = f"ch_{ch_idx}"

            theory_data = qge.generate_chapter_theory_and_cards(
                chapter_title=ch_title,
                chapter_text=ch_content[:3000],
                subject=subject,
                tier=academic_tier,
                chapter_index=ch_idx
            )

            ch_cards = theory_data.get("cards", [])
            all_cards.extend(ch_cards)

            chunks = MaterialParser.create_semantic_chunks(ch_content[:8000], chunk_size=400, overlap=40)[:15]
            try:
                db_pipeline.ingest_custom_chunks(
                    course_id=course_id,
                    chunks=chunks,
                    subject=subject,
                    academic_tier=academic_tier,
                    chapter_id=ch_id,
                    chapter_index=ch_idx
                )
            except Exception as ve:
                print(f"[ChromaDB] Vector ingestion warning: {ve}")

            processed_chapters.append({
                "chapter_id": ch_id,
                "chapter_index": ch_idx,
                "title": ch_title,
                "summary": theory_data.get("summary", ""),
                "objectives": theory_data.get("objectives", []),
                "cards": ch_cards,
                "deep_theory": theory_data.get("deep_theory", {}),
                "full_text": ch_content,
                "content_preview": ch_content[:400] + "..." if len(ch_content) > 400 else ch_content
            })

    # 3. Generate Assessment Items (Practice Quizzes + Threshold Final Exam)
    assessment = qge.generate_assessment_items(
        course_title=title,
        chapters=processed_chapters,
        subject=subject,
        tier=academic_tier
    )

    quizzes = assessment.get("quizzes", [])
    final_exam = assessment.get("finalExam", [])

    # 4. Assemble and persist course
    course_record = {
        "course_id": course_id,
        "title": title,
        "subject": subject,
        "academic_tier": academic_tier,
        "is_builtin": False,
        "description": f"Custom ingested curriculum for {title}.",
        "chapters_count": len(processed_chapters),
        "flashcards_count": len(all_cards),
        "quizzes_count": len(quizzes),
        "exam_questions_count": len(final_exam),
        "chapters": processed_chapters,
        "cards": all_cards,
        "quizzes": quizzes,
        "finalExam": final_exam
    }

    CourseManager.save_custom_course(course_record)
    return course_record


# --- INGESTION & COURSE REST ENDPOINTS ---

@app.post("/api/material/ingest")
async def ingest_material_json(payload: IngestMaterialPayload):
    """API endpoint to ingest raw text, notes, or syllabus JSON."""
    try:
        course = process_and_ingest_material(
            title=payload.title,
            subject=payload.subject,
            academic_tier=payload.academic_tier,
            raw_text=payload.raw_text
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
    academic_tier: Optional[str] = Form("Standard")
):
    """API endpoint to upload PDF, TXT, or Markdown documents for automated ingestion."""
    try:
        contents = await file.read()
        filename = (file.filename or "uploaded_document").lower()
        clean_title = title.strip() if (title and title.strip()) else os.path.splitext(file.filename or "Uploaded Material")[0]
        
        if filename.endswith(".pdf"):
            extracted_text = MaterialParser.extract_text_from_pdf_bytes(contents)
        else:
            extracted_text = contents.decode("utf-8", errors="replace")
            
        course = process_and_ingest_material(
            title=clean_title,
            subject=subject or "General",
            academic_tier=academic_tier or "Standard",
            raw_text=extracted_text
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

@app.get("/api/material/courses")
async def get_all_courses():
    """Lists all available standard and ingested custom courses."""
    return {"courses": CourseManager.list_all_courses()}

@app.get("/api/material/course/{course_id}")
async def get_course_detail(course_id: str):
    """Retrieves full course structure and theory chapters for a specific course ID."""
    course = CourseManager.get_course_by_id(course_id)
    if not course:
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
        if not model:
            raise ValueError("Offline mode: running local deterministic diagnostic engine.")
        diag_res   = model.invoke([HumanMessage(content=diagnostic_prompt)])
        clean_json = diag_res.content.replace("```json", "").replace("```", "").strip()
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
        is_correct = (norm_student == norm_expected) or (payload.student_raw_input.strip().lower() == payload.expected_answer.strip().lower())
        base_accuracy = 100.0 if is_correct else 0.0
        error_severity = 0.0 if is_correct else 0.8
        gap_analysis  = sanitize_gap_analysis(
            f"The student wrote '{payload.student_raw_input}', but the approach or result "
            f"does not yet satisfy the problem requirements. Review the governing relationship "
            f"for this question type.",
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
    # STAGE 3 — Mamdani-Calibrated Gemini Hint
    # ══════════════════════════════════════════════════════════════════════════════
    hint_response = ""
    if not is_correct:
        shared_context = (
            f"SUBJECT: {payload.current_subject} | LEVEL: {payload.current_tier}\n"
            f"QUESTION: {payload.question_text}\n"
            f"STUDENT'S ANSWER: {payload.student_raw_input}\n\n"
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

        if degree_of_failure >= 60.0 or error_severity >= 0.7:
            # ── INTERVENTION REQUIRED: Structured conceptual walkthrough ─────
            hint_prompt = (
                "You are an academic remediation tutor. The Mamdani Fuzzy System has classified "
                "this student in the 'Intervention Required' tier — they need structured guidance.\n\n"
                + shared_context +
                f"KNOWN MISCONCEPTION PATTERN: {payload.hint_misconception or 'general conceptual gap'}\n\n"
                "DIRECTIVE:\n"
                "1. In ONE sentence, confirm exactly what the student got wrong (reference their answer).\n"
                "2. Explain the governing formula or concept in plain language.\n"
                "3. Walk through the setup steps (identify variables, choose the right operation) "
                "   WITHOUT computing or stating the final numerical answer.\n"
                "4. End with one encouraging prompt for the student to finish the calculation themselves.\n"
                "STRICT RULE: Never state the final answer, exact result, or completed substitution.\n"
                "Do NOT be generic. Every sentence must be about THIS student's specific mistake."
                + HINT_FORMAT_DIRECTIVE
            )
        else:
            # ── DEVELOPING: Targeted Socratic nudge ──────────────────────────
            hint_prompt = (
                "You are a Socratic tutoring assistant. The Mamdani Fuzzy System has classified "
                "this student in the 'Developing' tier — they are close but need a targeted nudge.\n\n"
                + shared_context +
                f"KNOWN MISCONCEPTION PATTERN: {payload.hint_misconception or 'general conceptual gap'}\n\n"
                "DIRECTIVE:\n"
                "1. In ONE sentence, pinpoint exactly what is wrong in the student's answer "
                "   (reference their specific words/values).\n"
                "2. Ask ONE Socratic question that leads them to discover the correct approach "
                "   without giving away the answer or formula.\n"
                "3. Optionally add a one-sentence conceptual reminder.\n"
                "STRICT RULE: Never state the final answer, exact result, or completed substitution.\n"
                "Do NOT be generic. Every sentence must address THIS student's specific error."
                + HINT_FORMAT_DIRECTIVE
            )

        try:
            response      = model.invoke([HumanMessage(content=hint_prompt)])
            hint_response = sanitize_hint_text(response.content, payload.expected_answer)
        except Exception as e:
            print("GEMINI API ERROR IN EVALUATE-SHORT-ANSWER:", e)
            if degree_of_failure >= 60.0:
                hint_response = sanitize_hint_text(
                    "## Concept Review\n"
                    f"- **Focus:** {gap_analysis}\n"
                    f"- **Key relationship:** {payload.hint_formula or 'Identify how the given quantities relate.'}\n"
                    "- **Next step:** Substitute the known values and finish the calculation on your own.",
                    payload.expected_answer,
                )
            else:
                hint_response = sanitize_hint_text(
                    "## Socratic Nudge\n"
                    "- You are close — re-check whether you applied the correct operation.\n"
                    f"- **Common pitfall:** {payload.hint_misconception or 'Double-check calculation order.'}\n"
                    "- What relationship between the given values might you have overlooked?",
                    payload.expected_answer,
                )
    else:
        hint_response = (
            f"Correct! {linguistic_remark} "
            f"Fuzzy Mastery Score: {fuzzy_score}% — {performance_tier}."
        )

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
            topic = repo_q.get("moduleOrigin", "Unknown Topic")
            q_text = repo_q.get("text", "Unknown Question")
            formula = repo_q.get("formula", "")
            misconception = repo_q.get("misconception", "")
            
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)