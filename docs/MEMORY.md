# 🧠 Project Memory — Learning Companion

> This file is the project's working memory: quick facts, conventions, key decisions, and
> gotchas. Read this first when you open the repo to get oriented fast. It is a companion
> to [ARCHITECTURE.md](./ARCHITECTURE.md) (how it works), [API.md](./API.md) (endpoints),
> [DESIGN.md](./DESIGN.md) (UI), [DATA.md](./DATA.md) (knowledge base), and
> [SETUP.md](./SETUP.md) (running it).

---

## 1. One-Paragraph Summary

AURA is a **glass-box AI tutoring platform**: the student picks a subject
(Physics / Biology / Mathematics) and a level (Class 10 / Class 11-12 / Undergraduate),
then studies flashcards, practices short answers, takes a timed exam, and chats with an
agentic tutor. Every interaction is scored by a **Mamdani-style fuzzy inference system**
(accuracy × latency → mastery tier), answered using **Gemini 2.5 Flash** grounded in
**ChromaDB textbook RAG**, and routed through a **LangGraph state machine** that visibly
reports *which cognitive node* is active (Surface / Deep / Direct) — that's the "glass box".

---

## 2. Quick Facts

| Fact | Value |
| --- | --- |
| Repo branches | `main` (stable), `feature-landing-page` (current work) |
| Frontend | React 18 · Vite 5 · Tailwind 3 · lucide-react |
| Backend | FastAPI · uvicorn · LangGraph · LangChain · Gemini 2.5 Flash |
| Vector store | ChromaDB persistent, collection `curriculum_repository` |
| Fuzzy engine | Custom Mamdani-style system in `backend/fuzzy_engine.py` |
| Backend port | `127.0.0.1:8000` |
| Frontend port | `5173` (vite, `host: true`) |
| Env keys used | `GEMINI_API_KEY` or `GOOGLE_API_KEY` (`.env`) |
| Python env | `venv/` in project root (Python 3.13) |

---

## 3. Key File Map (What to Touch for What)

| "I want to…" | Edit |
| --- | --- |
| Add an API endpoint | `backend/app.py` |
| Change tutor routing / prompts | `backend/tutor_graph.py` |
| Tune grading math | `backend/fuzzy_engine.py` |
| Change flashcards logic | `backend/flashcard_builder.py` |
| Edit static quiz/exam bank | `backend/theory_repo.py` |
| Add sanitization rules for hints | `backend/hint_utils.py` |
| Change dashboard UI / views | `frontend/src/App.jsx` |
| Change landing page UI | `frontend/src/components/LandingPage.jsx` |
| Change animations / glass styles | `frontend/src/index.css` |
| Rebuild ChromaDB from textbooks | `backend/database_ingest.py` (run as script) |

---

## 4. Architecture in 5 Bullets

1. **Two processes:** FastAPI backend + Vite React frontend, all traffic is JSON over HTTP.
2. **One state machine:** `tutor_graph.py` = retrieve → analyze (fuzzy) → route →
   surface/deep/direct discussion node. Exported as `compiled_tutor_app`.
3. **One scoring brain:** `FuzzyMarkingSystem.evaluate_performance(accuracy, latency)`
   returns `{fuzzy_score, performance_tier, linguistic_remark}` — used everywhere.
4. **One knowledge base:** ChromaDB `curriculum_repository` seeded from OpenStax `.txt`
   files; queried with `subject` + `academic_tier` metadata filters.
5. **One UI surface reuse:** `App.jsx` owns the dashboard; `LandingPage.jsx` owns
   marketing + subject/level selection; everything is the light Japandi "washi paper"
   surface (`sand` ink/paper + `ember` / `olive` / `clay` naturals).

---

## 5. Conventions & Rules

- **Python:** module-level files in `backend/` (no packages — imports are flat, e.g. `from
  fuzzy_engine import ...`). Import paths assume you run from `backend/`.
- **API payloads:** always Pydantic `BaseModel` classes (`ChatSessionPayload`,
  `ShortAnswerPayload`, `ExamSubmissionPayload`, `TheoryRequestPayload`).
- **Tiers are literal strings:** `"Class 10"`, `"Class 11-12"`, `"Undergraduate"`.
- **Subjects are literal strings:** `"Physics"`, `"Biology"`, `"Mathematics"`.
- **JSON field names:** frontend uses camelCase in payloads (`current_subject`,
  `current_tier`, `time_taken`, `consecutive_errors`); backend returns snake_case
  (`fuzzy_score`, `performance_tier`, `gap_analysis`).
- **Every LLM call must have a fallback path** — no API key must mean graceful degradation.
- **Hints never leak the answer** — run output through `hint_utils.sanitize_*`.
- **Flashcards are cached** per `(subject, tier)`; don't call Gemini in a loop.
- **LLM model:** `gemini-2.5-flash` everywhere (do not diverge without reason).
- **UI theme tokens:** the frontend uses the custom Japandi palette in
  `frontend/tailwind.config.js` (`japandiPalette`) — `sand` for paper/ink neutrals (replaced
  `slate`), `ember` for primary/Physics (replaced `blue`), `olive` for Biology (replaced
  `emerald`), `clay` for Mathematics/hints (replaced `purple` + `rose`), Tailwind
  `amber`/`yellow` kept for warnings and ratings. The neutral ramp is **inverted** (`sand-50` =
  sumi ink, `sand-950` = rice paper), `text-white` is only valid on `*-600` accent fills, and
  overlay scrims are ink (`bg-sand-50/65`…`/85`). Don't add the retired cool families; see
  [DESIGN.md](./DESIGN.md) §2.
---

## 6. Decision Log (Why It's Built This Way)

| Decision | Rationale |
| --- | --- |
| Mamdani fuzzy engine instead of pure heuristic thresholds | Smooth continuous grading; a single scoring brain shared by chat, hints, and exams |
| ChromaDB + OpenStax textbooks | Retrieval must ground answers in *verified* curriculum - RAG over hallucination |
| Three-tier routing (surface/deep/remedial) | Matches Bloom-style scaffolding; "give me the answer" is treated as a *remedial* signal, not success |
| Answer-leak sanitizers | Keeps the Socratic loop honest: hints guide, never reveal |
| Single-file `App.jsx` dashboard | Fast prototyping for a class project; trade-off is size (~1460 lines) |
| In-memory flashcard cache | Avoids burning Gemini quota on identical `(subject, tier)` requests |
| `FALLBACK_CURRICULUM` hardcoded in frontend | Dashboard still renders useful content when backend is offline |

---

## 7. Gotchas & Troubleshooting

| Symptom | Cause / Fix |
| --- | --- |
| `chroma_knowledge_base` exists twice (root + `backend/`) | Only the **root** one is the live DB (`database_ingest.py` resolves to `<root>/chroma_knowledge_base`). The `backend/` one is stale/leftover. |
| `/api/tutor/*` returns 404 from frontend | Backend must run from `backend/` (or as `python backend/app.py`) so flat imports resolve. |
| Chat returns canned fallback text | No `GEMINI_API_KEY` set, or `.env` not loaded. Put `.env` in root **and/or** `backend/`. |
| RAG returns only 1 generic chunk | `curriculum_repository` empty → re-run `python backend/database_ingest.py`. |
| Duplicate flashcard topics | Heuristic dedupes by `_extract_topic`; boilerplate filtered by `_is_educational_content`. |
| Port 5173 already used | Vite picks next free port; check the console URL. |
| `npm install` needed | Run once; `npm run dev` thereafter (or `-- --force` to bypass cache). |
| Landing Page vs Dashboard mismatch | Landing lives in `components/LandingPage.jsx`; submit/subject handlers are passed in as props from `App.jsx`. |

---

## 8. Current Work Context

- **Active branch:** `feature-landing-page` (merged with `main`).
- **Recent changes:** responsive fixes on small screens, landing-page image rollback/fix,
  scroll animations (`Reveal.jsx`, `animate-*` utilities), subject/level selection modal,
  gallery lightbox with keyboard navigation, the warm "ember" retheme of the whole frontend
  (`sand` / `ember` / `olive` / `clay` tokens), and then the light **Japandi** retheme
  (washi paper + sumi ink, inverted neutral ramp, matte panels — [DESIGN.md](./DESIGN.md) §2).
- **Financial/cost note:** flashcard generation and hint generation hit the Gemini API;
  throttled by in-memory caching but there is **no persistent user database yet** — state
  is session-only on the frontend.

---

## 9. Future Ideas (not committed)

- Persist student profiles / history to a real DB (currently in-memory only).
- Serve ChromaDB from a single canonical path and delete the stale copy.
- Split `App.jsx` dashboard into route-based components.
- Add streaming responses (`SSE`/`websocket`) for nicer chat UX.
- Unit tests for `fuzzy_engine.py` and `hint_utils.py` (pure functions, easy to cover).