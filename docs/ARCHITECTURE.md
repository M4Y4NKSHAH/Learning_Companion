# 🧠 Learning Companion — System Architecture

> **The "Agentic Socratic Tutoring Platform" (AURA)**  
> A multi-agent adaptive educational platform featuring:
> 1. **Pedagogical & Information Guardrails** that enforce strict academic tier ceilings (preventing Class 12 calculus/formalisms from leaking into Class 9) and deflect off-topic queries.
> 2. **Authoritative Course Grounding** using ingested textbooks as the Primary Ground Truth via Hybrid RAG (BM25 + ChromaDB) with zero cross-chapter leakage.
> 3. **Offline Local Inference Engine** via Ollama (`llama3.2:3b`) on consumer GPUs (RTX 2050 4GB) with zero cloud token costs, backed by Gemini Cloud and rule-based fallbacks.
> 4. **Mamdani Fuzzy Inference Brain** that evaluates student mastery and guides cognitive routing in real-time.

---

## 1. High-Level Architecture Overview

```text
┌────────────────────────────────────────────────────────┐
│               FRONTEND (React 18 + Vite)               │
│               Japandi Washi Design System              │
│       Port 5173  ·  Glass-Box Cognitive Telemetry      │
└───────────────────────────┬────────────────────────────┘
                            │ HTTP JSON (/api/tutor/*, /api/material/*)
                            ▼
┌────────────────────────────────────────────────────────┐
│                 BACKEND (FastAPI Server)               │
│                    Port 127.0.0.1:8000                 │
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │     LangGraph Cognitive State Machine Engine     │  │
│  │   Context Retriever ──► Analyze Depth & Mamdani  │  │
│  │         │                                        │  │
│  │         ├──► [Course Guardrail Deflector Node]   │  │
│  │         ├──► [Socratic Hint Generator Node]      │  │
│  │         ├──► [Surface Discussion Node]           │  │
│  │         ├──► [Deep Analytical Discussion Node]   │  │
│  │         └──► [Direct Explainer Solution Node]    │  │
│  └──────────────────────────────────────────────────┘  │
│                                                        │
│  ┌──────────────────────┐    ┌──────────────────────┐  │
│  │ Pedagogical Engine   │    │ Mamdani Fuzzy System │  │
│  │ • Grade Tier Ceiling │    │ • Accuracy (0-100%)  │  │
│  │ • Primary Source RAG │    │ • Latency & Attempts │  │
│  │ • Off-Topic Filter   │    │ • Monotonic Penalty  │  │
│  │ • Output Sanitizer   │    │ • 4 Performance Tiers│  │
│  └──────────────────────┘    └──────────────────────┘  │
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │             Multi-Tier LLM Dispatcher            │  │
│  │  Tier 1: Local Ollama (llama3.2:3b, 100% Offline)│  │
│  │  Tier 2: Cloud Gemini 2.5 Flash (When Available) │  │
│  │  Tier 3: Rule-Based Curated Fallback Matrix      │  │
│  └──────────────────────────────────────────────────┘  │
│                                                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │          Hybrid RAG Vector & Keyword Store       │  │
│  │  • BM25 Keyword Search + ChromaDB Embeddings     │  │
│  │  • Chapter-Level Isolation (Zero-Leakage Chunks) │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
```

---

## 2. Backend Module Map

| File | Core Responsibility |
| --- | --- |
| `backend/app.py` | FastAPI application, CORS middleware, route handlers (`/api/tutor/*`, `/api/material/*`), background ingestion worker. |
| `backend/tutor_graph.py` | LangGraph `StateGraph` definition: 6 stateful nodes, Mamdani evaluation, guardrail deflection routing, exports `compiled_tutor_app`. |
| `backend/pedagogical_guardrails.py` | Grade tier normalization (`introductory`, `standard`, `advanced`), off-topic pattern matching, grounded prompt construction, and post-generation calculus filtering. |
| `backend/local_llm_service.py` | `LocalLLMService`: Connects to local Ollama instance (`http://localhost:11434`) running `llama3.2:3b` with zero cloud token consumption and GPU acceleration. |
| `backend/course_manager.py` | Enterprise course lifecycle manager: handles persistence, disk indexing of custom user courses, and standard built-in curriculum. |
| `backend/material_parser.py` | Algorithmic document parser: cleans raw text, prunes front/back matter clutter, segments continuous text into non-overlapping chapters with sliding window chunking. |
| `backend/question_generator.py` | `QuestionGeneratorEngine`: Single-pass curriculum blueprints, chapter theory synthesis, practice quizzes, and summative final exam generation. |
| `backend/database_ingest.py` | `DatabaseIngestPipeline`: Dual-engine BM25 keyword ranker + ChromaDB persistent vector storage with strict chapter-level namespaces. |
| `backend/fuzzy_engine.py` | `FuzzyMarkingSystem`: Mamdani fuzzy inference system evaluating accuracy, latency, attempt count, and error severity. |
| `backend/hint_utils.py` | Bidirectional answer-leak sanitization (`sanitize_hint_text`, `sanitize_gap_analysis`), string similarity algorithms, and prompt formatting directives. |
| `backend/theory_repo.py` | Static `FLASHCARD_REPOSITORY` holding built-in fallback question banks and flashcards. |
| `backend/analytics_db.py` | Persistent SQLite analytics database tracking student attempts, mastery trajectories, and error severity metrics. |

---

## 3. Pedagogical & Information Guardrails Engine

The pedagogical engine (`backend/pedagogical_guardrails.py`) enforces strict academic boundaries to prevent cognitive overload or off-topic drift:

### 3.1 Academic Tier Ceilings

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ 1. INTRODUCTORY (Class 9–10 / Secondary)                                    │
│ • Audience: High school students (ages 14–16).                              │
│ • Ceiling: Basic algebra, arithmetic ratios, qualitative principles.       │
│ • STRICT PROHIBITIONS: NO calculus (dy/dx, integrals), NO tensors,         │
│   NO university-level formalisms or thermodynamic potentials.               │
│ • MANDATORY REQUIREMENTS: Everyday intuitive analogies (swings, cars).      │
├─────────────────────────────────────────────────────────────────────────────┤
│ 2. STANDARD (Class 11–12 / Senior Secondary)                                │
│ • Audience: College-prep high school students (ages 16–18).                 │
│ • Ceiling: Vector mechanics, single-variable differential/integral calculus.│
│ • MANDATORY: Explicit parameter definitions with standard SI units.        │
├─────────────────────────────────────────────────────────────────────────────┤
│ 3. ADVANCED (Undergraduate / University)                                    │
│ • Audience: University engineering and science undergraduates.              │
│ • Ceiling: Multivariate calculus, differential equations, tensors.          │
│ • MANDATORY: First-principles formal derivations and boundary invariance.   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Authoritative Source File as Ground Truth
In `construct_grounded_system_prompt()`, the ingested course text is injected under the header:
```text
══════════════════════════════════════════════════════════════════════════════
PRIMARY GROUND TRUTH: INGESTED COURSE MATERIAL (TEXTBOOK)
══════════════════════════════════════════════════════════════════════════════
[Retrieved textbook excerpts from student's active chapter]
```
The model is strictly prohibited from introducing unverified outside trivia or hallucinated theories.

### 3.3 Information Guardrails & Deflection
- Evaluates queries against `OFF_TOPIC_PATTERNS` (gaming, entertainment, movies, social media, politics, malware, crypto).
- When triggered, routes directly to the **`Course Guardrail Deflector`** node:
  ```text
  **🎯 Course Guardrail Notice**:
  That inquiry falls outside our curriculum scope for **[Course]** ([Chapter]).
  Let's redirect our focus back to the core principles of **[Chapter]**.
  ```
- **Zero Token Cost**: Deflection executes instantly without calling LLM APIs.

### 3.4 Post-Generation Safety Filter
`filter_for_grade_level(response_text, tier)` inspects the generated output:
- For Class 9–10 learners, any accidental calculus differentials (`dv/dt`, `dy/dx`, `\int`) are automatically sanitized into intuitive rate-of-change expressions.

---

## 4. The LangGraph Tutor State Machine

Defined in `backend/tutor_graph.py`. A typed state dictionary `AgentState` flows through the compiled graph:

```text
               START
                 │
                 ▼
      ┌─────────────────────┐
      │ 1. retrieve_context │ ──► Hybrid BM25 + ChromaDB retrieval with chapter isolation
      └──────────┬──────────┘
                 │
                 ▼
      ┌─────────────────────┐
      │  2. analyze_depth   │ ──► Guardrail check + Mamdani fuzzy scoring + intent detection
      └──────────┬──────────┘
                 │ (conditional edge via route_after_analysis)
                 │
   ┌─────────────┼─────────────┬─────────────────┬─────────────────┐
   │             │             │                 │                 │
   ▼             ▼             ▼                 ▼                 ▼
┌──────────────┐ ┌───────────┐ ┌───────────────┐ ┌───────────────┐ ┌────────────────┐
│ guardrail_   │ │ socratic_ │ │ surface_      │ │ deep_         │ │ direct_        │
│ deflection   │ │ hint      │ │ discussion    │ │ discussion    │ │ explanation    │
│ (off-topic   │ │ (nudge,   │ │ (intuitive    │ │ (derivations, │ │ (explicit full │
│  redirection)│ │  no leaks)│ │  analogy)     │ │  equations)   │ │  worked answer)│
└──────┬───────┘ └─────┬─────┘ └───────┬───────┘ └───────┬───────┘ └────────┬───────┘
       │               │               │                 │                  │
       └───────────────┴───────────────┼─────────────────┴──────────────────┘
                                       ▼
                                      END
```

---

## 5. Multi-Tier Inference Execution

Every discussion and hint node in `tutor_graph.py` dispatches generation through `_execute_tutor_generation()`:

1. **Tier 1 (Local Ollama Engine)**:
   - Uses `LocalLLMService` to query `http://localhost:11434/api/generate` with model `llama3.2:3b`.
   - Runs with ~2.0 GB VRAM footprint on consumer GPUs (NVIDIA RTX 2050 4GB).
   - Zero API tokens consumed, 100% offline capability.
2. **Tier 2 (Gemini Cloud Fallback)**:
   - If local Ollama is not active and `GEMINI_API_KEY` is present, falls back to `gemini-2.5-flash`.
3. **Tier 3 (Curated Rule-Based Fallback)**:
   - If neither LLM is available, returns deterministic, curriculum-grounded pedagogical clues with zero disruption.

All tiers pass output through `filter_for_grade_level()` and `sanitize_hint_text()`.

---

## 6. Hybrid RAG & Dynamic Chapter Ingestion

- **Dual-Engine Search**: Combines BM25 lexical ranking (exact mathematical terms, laws, symbols) with ChromaDB dense vector embeddings (`all-MiniLM-L6-v2` / Chroma default).
- **Chapter Isolation**: Every chunk is indexed with metadata tags:
  ```json
  {
    "course_id": "custom_phy_89a12c",
    "chapter_id": "ch_2",
    "chapter_index": 2,
    "chapter_title": "Newton's Laws of Motion",
    "academic_tier": "Class 9",
    "subject": "Physics"
  }
  ```
- Retrieval queries enforce `course_id` and `chapter_id` filters, guaranteeing **zero cross-chapter leakage**.

### 6.1 Smart Chapter Segregation & Domain Auto-Detection

To prevent textbook front-matter, copyright boilerplate, and fragmented subsection tables from polluting courses:

1. **Automatic Subject & Domain Detection (`MaterialParser.detect_subject`)**:
   - Inspects the document title and text against domain-specific lexical indicators (e.g., `algorithm`, `computational`, `data structure`, `boolean`, `compiler` $\rightarrow$ Computer Science; `integral`, `matrix` $\rightarrow$ Mathematics; `velocity`, `thermodynamics` $\rightarrow$ Physics).
   - Dynamically overrides incorrect or default UI dropdown selections, preventing Computer Science books from ever being classified as Physics.

2. **Front-Matter & TOC Pruning (`MaterialParser.strip_front_matter_and_toc`)**:
   - Scans the document head and automatically discards copyright notices, publisher legal agreements (e.g. Creative Commons), author prefaces, and condensed Table of Contents summaries.
   - Begins chapter extraction strictly at the first authentic instructional chapter body (e.g., `1.1` or `Chapter 1`).

3. **Major Chapter Aggregation (`MaterialParser.aggregate_into_major_chapters`)**:
   - When textbooks structure content with numbered decimal sections (`1.1`, `1.2`, `1.3`, `2.1`, `2.2`), the parser aggregates all sub-sections into their parent major chapter (`1.x` $\rightarrow$ Chapter 1, `2.x` $\rightarrow$ Chapter 2, etc.).
   - Prunes trailing end-of-chapter review questions, self-quizzes, and index listings from the core theoretical body.
   - Strictly enforces heading validation requiring meaningful alphabetic tokens, preventing accidental table row numbers (`1. 2.`) or software versions (`4.0`) from spawning false chapters.

4. **Course Lifecycle & Disk Deduplication (`CourseManager.cleanup_duplicate_courses`)**:
   - Automatically maintains a clean single entry per course title on disk, overwriting existing course IDs on re-upload and removing legacy duplicate custom courses.


---

## 7. Automated Test Suite & Quality Assurance

The test suite in `backend/tests/` maintains a **100% pass rate** across 20 unit and integration tests:

| Test Module | Coverage | Status |
| --- | --- | --- |
| `test_pedagogical_guardrails.py` | Tier normalization, Class 9 vs Class 12 ceiling enforcement, off-topic deflection, post-generation calculus filtering, LangGraph guardrail routing. | **PASSED** (8/8) |
| `test_tier3_features.py` | BM25 keyword ranker, SQLite analytics database attempt recording. | **PASSED** (2/2) |
| `test_tier1_features.py` | Semantic similarity, SM-2 spaced repetition interval calculation, chapter-grounded card generation. | **PASSED** (3/3) |
| `test_section_optimization.py` | Academic header detection, fragment consolidation, cognitive chapter chunking. | **PASSED** (3/3) |
| `test_content_aware_qg.py` | Fact extraction, content-grounded assessment items, sliding overlap chunking. | **PASSED** (3/3) |
| `test_fuzzy_extended.py` | Multi-parameter Mamdani fuzzy inference edge cases. | **PASSED** (1/1) |