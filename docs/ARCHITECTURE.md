# 🧠 Learning Companion — System Architecture

> The "Agentic Socratic Tutoring Platform" (AURA). A multi-agent adaptive educational
> platform where a fuzzy-logic brain decides *how* to teach, a LangGraph tutor decides
> *what* to say, and a ChromaDB RAG layer grounds every answer in verified textbook content.

---

## 1. High-Level Overview

The application is split into two processes that talk over HTTP:

```
┌─────────────────────────────┐          ┌──────────────────────────────┐
│        FRONTEND (Vite)      │          │         BACKEND (FastAPI)    │
│  React 18 + Tailwind 3      │  HTTP    │  Port 127.0.0.1:8000        │
│  Port 5173                  │ ───────► │  LangGraph · LangChain ·     │
│                             │  JSON    │  Gemini 2.5 Flash · ChromaDB │
└─────────────────────────────┘          └──────────────────────────────┘
```

- **Frontend** (`frontend/`) — React SPA. Renders the marketing **Landing Page**, then
  the **Glass-Box Dashboard** (Study Deck, Practice Lab, Threshold Exam, chat). All
  intelligence lives server-side; the UI only calls `/api/tutor/*`.
- **Backend** (`backend/`) — FastAPI app exposing 5 tutor endpoints. It orchestrates a
  LangGraph state machine, a Mamdani-style fuzzy inference system, a ChromaDB vector
  store, and the Gemini LLM to generate adaptive tutoring responses.

---

## 2. Backend Module Map

| File | Responsibility |
| --- | --- |
| `backend/app.py` | FastAPI entrypoint, CORS, Pydantic schemas, 5 endpoint routers, RAG lookup factory |
| `backend/tutor_graph.py` | LangGraph `StateGraph` — 5 nodes + conditional routing; exports `compiled_tutor_app` |
| `backend/database_ingest.py` | `DatabaseIngestPipeline` — builds/queries the ChromaDB `curriculum_repository` collection |
| `backend/fuzzy_engine.py` | `FuzzyMarkingSystem` — Mamdani-style fuzzy evaluation (accuracy × latency → score/tier) |
| `backend/flashcard_builder.py` | Heuristic `build_flashcards_from_chroma` + AI `generate_gemini_flashcards_from_chroma` with in-memory caching |
| `backend/hint_utils.py` | Answer-leak sanitization regexes + `HINT_FORMAT_DIRECTIVE` prompt boilerplate |
| `backend/theory_repo.py` | Static `FLASHCARD_REPOSITORY` — offline cards, quizzes & final-exam question bank |
| `backend/analytics.py` | `PathPerformanceAnalytics` — compares guided vs. direct learning pathways |

### Dependency flow

```
app.py ──► tutor_graph (compiled LangGraph app)
         ├─► database_ingest (ChromaDB RAG lookup)
         ├─► fuzzy_engine (Mamdani evaluation)
         ├─► flashcard_builder ──► database_ingest + theory_repo
         ├─► theory_repo (static question bank)
         ├─► hint_utils (sanitizers)
         └─► analytics (pathway improvement)
```

---

## 3. The LangGraph Tutor State Machine

Defined in `tutor_graph.py`. A typed state `AgentState` flows through the graph; each node
returns partial state updates which LangGraph merges.

### Node pipeline

```
 START
   │
   ▼
┌───────────────────────────┐
│ 1. retrieve_context       │  ChromaDB similarity search (subject + academic_tier filter)
│    "Context Retriever"    │  └► fills state.retrieved_curriculum
└───────────────────────────┘
   │
   ▼
┌───────────────────────────┐
│ 2. analyze_depth          │  Heuristic keyword analysis + Mamdani fuzzy scoring
│    "Route Planner"        │  └► sets depth_level ∈ {surface, deep, remedial}
└───────────────────────────┘
   │  (conditional routing via route_after_analysis)
   │
   ├───────────────┬────────────────────┐
   ▼               ▼                    ▼
┌──────────────┐ ┌──────────────────┐ ┌──────────────────┐
│ surface      │ │ deep             │ │ direct           │
│ discussion   │ │ discussion       │ │ explanation      │
│ (intuitive,  │ │ (formulas,       │ │ (give the answer │
│  analogy)    │ │  derivations)    │ │  step-by-step)   │
└──────────────┘ └──────────────────┘ └──────────────────┘
   │                │                    │
   └────────────────┴────────────────────┘
                     ▼
                    END  (answer returned to /api/tutor/chat)
```

### Routing heuristics (in `analyze_depth`)
- **Surrender keywords** (`"give me the answer"`, `"i don't know"`, `"solution"`, …)
  **OR** ≥1 consecutive error **OR** latency > 90s → `remedial` → `direct_explanation`
- Deep keyword phrases / word count ≥ 8 → `deep` (unless failure conditions)
- Otherwise → `surface`

### Model config
- LLM: `gemini-2.5-flash`
- Temperature varies by node: surface `0.3`, deep `0.2`, direct `0.1`
- API key from `GEMINI_API_KEY` or `GOOGLE_API_KEY` env var
- Every node has a **hardcoded fallback** so the app still works offline

---

## 4. RAG / Vector Store

- **Engine:** ChromaDB `PersistentClient`
- **DB path:** `<project_root>/chroma_knowledge_base` (resolved dynamically)
- **Collection:** `curriculum_repository`
- **Embeddings:** Chroma `DefaultEmbeddingFunction`
- **Ingestion:** paragraphs (`split("\n\n")`, length > 40 chars) → batch upsert (batch = 2000)
- **Metadata on every chunk:** `subject`, `academic_tier`, `grade_level`,
  `data_integrity_status="verified"`
- **Query filter:** `{"$and": [{"academic_tier": tier}, {"subject": subject}]}`, `n_results=3`

```
user question ──► embed ──► top-3 textbook chunks ──► injected into Gemini prompt ──► grounded answer
```
---

## 5. Fuzzy Evaluation Flow (Mamdani)

`FuzzyMarkingSystem.evaluate_performance(accuracy_pct, latency_seconds)`:

1. **Fuzzify accuracy** → membership sets: High Mastery / Developing / Intervention Required
2. **Fuzzify latency** → membership sets: Fast / Slow pacing
3. **Rule matrix** (min/max Mamdani intersection) → active rule weights
4. **Defuzzify** → centroid center-of-gravity approximation → final score (0–100)
5. **Map** to one of 4 performance tiers:

| Score | Tier |
| --- | --- |
| ≥ 85 | High Mastery |
| ≥ 70 | Moderate Mastery |
| ≥ 50 | Developing |
| < 50 | Intervention Required |

The same evaluator powers `/chat` routing, short-answer hints, and final-exam grading.

---

## 6. Frontend Structure

```
frontend/
├─ index.html                # Vite shell, loads Outfit font, #root
├─ vite.config.js            # port 5173, host: true
├─ tailwind.config.js        # theme tokens
├─ postcss.config.js
└─ src/
   ├─ main.jsx               # React root (StrictMode)
   ├─ App.jsx                # Dashboard + app shell (single-file surface)
   ├─ index.css              # Tailwind + washi-panel/halo/flip-card/animation utilities
   ├─ components/
   │  ├─ LandingPage.jsx     # Marketing page: hero, subjects/levels, modal, gallery
   │  └─ Reveal.jsx          # Scroll-triggered reveal wrapper
   └─ assets/                # heroImage.png + gallery1–5.png
```

### Dashboard views (`App.jsx`)
| View | Purpose |
| --- | --- |
| `Study Deck` | Flip-card flashcards (heuristic or Gemini-generated) |
| `Practice Lab` | Quiz questions + free-answer text field → hint feedback loop |
| `Threshold Exam` | Timed final exam → graded report with remediation plan |
| Chat pane | Open-ended conversation driven by the LangGraph state machine |

---

## 7. Request/Response Flow (End-to-End Example)

```
1. User picks "Physics — Class 10" on Landing Page
2. App.jsx → POST /api/tutor/load-theory            → cards, quizzes, finalExam
3. Study Deck → POST /api/tutor/generate-flashcards → Gemini RAG cards (cached)
4. Practice Lab answer → POST /api/tutor/evaluate-short-answer → fuzzy grade + sanitized hint
5. Threshold Exam → POST /api/tutor/evaluate-exam   → fuzzy grade + remediation hint + analytics
6. Chat message → POST /api/tutor/chat              → LangGraph-routed tutor reply + telemetry
```

---

## 8. Component / Data Lifecycle Facts

- **Flashcards** are cached in-memory per `(subject, tier)` key
  (`_flashcard_cache`, `_gemini_flashcard_cache`) to avoid repeat LLM calls.
- **Theory content** falls back to a hardcoded `FALLBACK_CURRICULUM` in `App.jsx`
  if the backend is unreachable.
- **All backend modules** degrade gracefully when no Gemini API key is present
  (they return canned, curriculum-aware fallback responses).

See also: [`API.md`](./API.md) for endpoint contracts, [`SETUP.md`](./SETUP.md) to run it,
[`DATA.md`](./DATA.md) for the knowledge-base structure, and
[`MEMORY.md`](./MEMORY.md) for quick project context.