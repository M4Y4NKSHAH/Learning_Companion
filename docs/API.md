# 🔌 API Reference — Learning Companion Backend

> FastAPI backend, served at `http://127.0.0.1:8000`. All endpoints are `POST` + JSON.
> CORS is wide open (`allow_origins=["*"]`) for the dev frontend on port 5173.

---

## 1. Endpoint Overview

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/material/ingest` | Ingest raw text/notes/syllabus into structured chapters, flashcards & tests |
| POST | `/api/material/upload` | Upload PDF, TXT, or Markdown document for automated course generation |
| GET | `/api/material/courses` | List all available standard and custom ingested courses |
| GET | `/api/material/course/{course_id}` | Retrieve full course outline, chapters, objectives and assessment items |
| DELETE | `/api/material/course/{course_id}` | Delete a user-created custom course |
| POST | `/api/tutor/load-theory` | Load cached/AI cards, quizzes & final exam (supports custom `course_id`) |
| POST | `/api/tutor/generate-flashcards` | Force-generate Gemini RAG flashcards (max 3) |
| POST | `/api/tutor/chat` | LangGraph-routed adaptive tutor turn |
| POST | `/api/tutor/evaluate-short-answer` | Grade free-text answer + produce sanitized Socratic hint |
| POST | `/api/tutor/evaluate-exam` | Grade the timed final exam + remediation plan + analytics |

**Conventions**
- Request & response bodies are `application/json`.
- Tier strings: `"Class 10"` | `"Class 11-12"` | `"Undergraduate"`.
- Subject strings: `"Physics"` | `"Biology"` | `"Mathematics"`.
- No auth tokens. Errors degrade to fallback content, not 5xx (by design).

---

## 2. `POST /api/tutor/load-theory`

Loads the static theory deck, quizzes, and final exam. If Gemini cards were generated
before, returns them from the in-memory cache (`is_ai_generated=true`).

**Request body** (`TheoryRequestPayload`)

```jsonc
{
  "current_tier": "Class 10",
  "current_subject": "Physics"
}
```

**Response**

```jsonc
{
  "cards": [
    { "id": "p10_c1", "topic": "Newton's Second Law",
      "question": "What is the core formula for Newton's Second Law…?",
      "answer": "• Core Equation: Force = Mass x Acceleration (F = m x a).\n• …" }
  ],
  "quizzes": [
    { "id": "p10_q1", "text": "A 10kg structural mass…", "concept": "Newton's Second Law" }
  ],
  "finalExam": [
    { "qId": "p10_f1", "moduleOrigin": "Module 1: Newton's Second Law", "text": "…",
      "expected": "32", "formula": "Force = Mass x Acceleration (F = m x a)",
      "misconception": "Student might be dividing the variables…" }
  ],
  "is_ai_generated": false,      // true if served from _gemini_flashcard_cache
  "is_cached": false             // true if the AI cards cache already has this key
}
```

---

## 3. `POST /api/tutor/generate-flashcards`

Generates **exactly 3** flashcards using Gemini, grounded in ChromaDB chunks for the
subject/tier. Caches result in `_gemini_flashcard_cache[(subject, tier)]`.

**Request body** — same `TheoryRequestPayload` as §2.

**Response**

```jsonc
{
  "cards": [
    { "id": "ai_phy_cla_1", "topic": "…", "question": "…?", "answer": "• …", "source": "gemini_rag" }
  ],
  "cached": false,
  "source": "gemini_rag"
}
```

> If Gemini fails or no API key exists, it **falls back** to heuristic
> `build_flashcards_from_chroma(...)` (`id: "ch_…"`, source absent → `"chroma"`-style cards).

---

## 4. `POST /api/tutor/chat`

Runs one turn through the compiled LangGraph tutor. History (last **6** messages) is
replayed so the tutor has context.

**Request body** (`ChatSessionPayload`)

```jsonc
{
  "message": "Why does F = ma?",
  "time_taken": 12,            // seconds on this turn
  "consecutive_errors": 0,
  "current_tier": "Class 10",
  "current_subject": "Physics",
  "history": [
    { "sender": "user",  "text": "What is Newton's second law?" },   // or "student"
    { "sender": "tutor", "text": "It relates force, mass and acceleration…" } // or "ai"
  ]
}
```

**Response**

```jsonc
{
  "response": "Excellent question! Here's an intuitive map of F = ma…",
  "active_node": "Deep Inquiry Discussion Node",   // glass-box telemetry
  "depth_level": "deep",                            // surface | deep | remedial
  "remedial_triggered": false,
  "context_pulled": ["…retrieved textbook chunk…", "…"],
  "mamdani_evaluation": {
    "fuzzy_score": 90.0,
    "performance_tier": "High Mastery",
    "linguistic_remark": "Exemplary Performance: …",
    "degree_of_failure": 10.0
  }
}
```

> Fallback if the graph throws: `active_node = "Discussion Node"`,
> `depth_level = "surface"`, `mamdani_evaluation.fuzzy_score = 60.0`.
---

## 5. `POST /api/tutor/evaluate-short-answer`

3-stage pipeline: Gemini diagnostic grader → Mamdani fuzzy scoring → adaptive hint
(Intervention walkthrough **or** Developing Socratic nudge), with answer-leak
sanitization applied before returning.

**Request body** (`ShortAnswerPayload`)

```jsonc
{
  "question_text": "A 10kg structural mass experiences a constant acceleration of 5 m/s². Calculate the active net force …",
  "student_raw_input": "50",
  "expected_answer": "50",           // used ONLY to strip leaked answers from hints
  "seconds_spent": 25,
  "attempts_count": 1,
  "current_tier": "Class 10",
  "current_subject": "Physics",
  "hint_formula": "Force = Mass x Acceleration (F = m x a)",
  "hint_misconception": "Student might be dividing the variables…"
}
```

**Response**

```jsonc
{
  "is_correct": true,                 // exact/case-insensitive match with expected_answer
  "fuzzy_score": 84.2,
  "degree_of_failure": 15.8,
  "performance_tier": "Moderate Mastery",
  "linguistic_remark": "Proficient with Methodical Focus: …",
  "gap_analysis": "Review how the quantities in this problem relate…",
  "assigned_hint": "## Socratic Nudge\n- You are close — re-check whether you applied the correct operation.\n…"
}
```

> When `is_correct` is `true`, `assigned_hint` is a congratulation + fuzzy score line.
> `gap_analysis` is also sanitized via `sanitize_gap_analysis` — hints **never** contain
> the expected answer.

---

## 6. `POST /api/tutor/evaluate-exam`

Grades the timed threshold exam, computes growth analytics, and generates a
tier-appropriate remediation hint (Level 1 Foundation → Level 4 Advanced Challenge).

**Request body** (`ExamSubmissionPayload`)

```jsonc
{
  "correct_answers": 2,               // used only when question_details is empty
  "total_questions": 3,
  "total_elapsed_time": 90,
  "current_tier": "Class 10",
  "current_subject": "Physics",
  "mock_chat_history": [{ "sender": "student", "text": "…" }, …],  // for pathway analytics
  "question_details": [               // preferred over the nested counters above
    { "qId": "p10_f1", "is_correct": true, "attempts": 1, "latency_seconds": 20, "fuzzy_score": 88.0 }
  ]
}
```

**Response**

```jsonc
{
  "subject": "Physics",
  "grade_tier": "Class 10",
  "calculated_score": 74.5,
  "rating_tier": "Moderate Mastery",
  "mentor_remark": "Proficient with Methodical Focus: …",
  "remediation_hint": "## Level 3 – Efficiency Calibration\nGreat job! …",
  "growth_metrics": {
    "pathway_taken": "Pathway A: Guided Scaffolding (Theory + Mock Test + Final Exam)",
    "score_delta_pct": 4.5,
    "analytical_insight": "Moderate improvement. Scaffolding provided a steady conceptual foundation."
  }
}
```

> Without `question_details`, accuracy = `correct_answers / total_questions * 100` and
> average latency = `total_elapsed_time / total_questions`.
> Without `mock_chat_history`, the pathway is reported as
> "Pathway B: Direct Evaluation (No Mock Test)".

---

## 7. Internal Helpers (not endpoints)

| Function | Location | Use |
| --- | --- | --- |
| `execute_rag_vector_lookup(subject, tier, query)` | `app.py` | Factory for ChromaDB top-3 retrieval |
| `compiled_tutor_app.invoke(state)` | `tutor_graph.py` | Runs the LangGraph pipeline |
| `FuzzyMarkingSystem.evaluate_performance(acc, latency)` | `fuzzy_engine.py` | Score/tier/remark everywhere |
| `build_flashcards_from_chroma` / `generate_gemini_flashcards_from_chroma` | `flashcard_builder.py` | Card sources + caching |
| `sanitize_gap_analysis` / `sanitize_hint_text` | `hint_utils.py` | Anti-leak post-processing |

---

## 8. Frontend Consumption

`App.jsx` targets `http://127.0.0.1:8000` directly with `fetch()`:

- `load-theory` → `loadCurriculum(activeSubject, activeTier)` (line ~357)
- `generate-flashcards` → AI cards button (line ~391)
- `evaluate-short-answer` → Practice Lab submit (line ~444)
- `evaluate-exam` → Threshold Exam submit (line ~557)
- `chat` → chat send (line ~611)

All requests set `Content-Type: application/json`; failures display inline fallback
content rather than crashing the UI.

---

## 9. Quick Manual Smoke Test (PowerShell)

```powershell
$body = @{ message="Why does F = ma?"; time_taken=12; consecutive_errors=0;
           current_tier="Class 10"; current_subject="Physics"; history=@() } | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/tutor/chat -Method Post -Body $body -ContentType "application/json"
```

Interactive docs are also available at **`http://127.0.0.1:8000/docs`** (FastAPI Swagger UI).