# 🧠 Learning Companion (AURA)

> **Glass-Box Multi-Agent Socratic Tutoring Platform**  
> Powered by FastAPI, LangGraph, Local Ollama (`llama3.2:3b`), Google Gemini (`gemini-3.8-flash`), ChromaDB + BM25 Hybrid RAG, and React (Japandi Design System).

---

## 📖 Overview

**Learning Companion** is an intelligent, transparent educational platform designed to foster deep understanding through Socratic inquiry rather than passive answer retrieval.

Unlike traditional "black-box" LLM tutors, Learning Companion exposes its reasoning and cognitive routing in real-time through a **Glass-Box UI**:
- **Cognitive Routing Telemetry:** Watch the agent switch between *Course Guardrail Deflection*, *Socratic Hinting*, *Surface Analogy*, *Deep Decomposition*, and *Direct Instruction*.
- **Pedagogical Guardrails:** Enforces strict academic level ceilings. A Class 9 student will **never** receive Class 12 calculus ($\frac{dy}{dx}, \int$), tensors, or university jargon, while Class 12 students receive structured mathematical derivations.
- **Authoritative Course Grounding:** The student's initial uploaded course material serves as the Primary Ground Truth via Hybrid RAG (BM25 lexical ranking + ChromaDB vector embeddings) with strict chapter-level isolation.
- **100% Offline Local LLM:** Runs on consumer GPUs (NVIDIA RTX 2050 4GB) via Ollama (`llama3.2:3b`) with zero cloud token consumption and complete data privacy, backed by Gemini 3.8 Flash Cloud and rule-based fallbacks.
- **Mamdani Fuzzy Inference System:** Multi-parameter evaluation that dynamically computes student mastery, error severity, response latency, and monotonic hint penalties.
- **Japandi Aesthetic UI:** Minimalist, serene, and warm design engineered for calm, distraction-free study sessions.

---

## 🏗️ System Architecture

```text
                  +-----------------------------------+
                  |        React + Vite Frontend      |
                  |     (Japandi Design System)       |
                  +-----------------+-----------------+
                                    |
                            HTTP / REST APIs
                                    |
                  +-----------------v-----------------+
                  |          FastAPI Server           |
                  |        (backend/app.py)           |
                  +-----------------+-----------------+
                                    |
        +---------------------------+---------------------------+
        |                           |                           |
+-------v-------+           +-------v-------+           +-------v-------+
| LangGraph     |           | Pedagogical   |           | Hybrid RAG    |
| Multi-Agent   |           | & Info        |           | BM25 Keyword  |
| State Machine |           | Guardrails    |           | + ChromaDB    |
+-------+-------+           +-------+-------+           +---------------+
        |                           |
        +-------------+-------------+
                      ▼
        +---------------------------+
        | Multi-Tier LLM Engine     |
        | 1. Local Ollama (3B, 0$)  |
        | 2. Cloud Gemini 3.8 Flash |
        | 3. Curated Rule Matrix    |
        +---------------------------+
```

---

## 📁 Repository Structure

```text
Learning_Companion/
├── docs/                           # Comprehensive technical documentation
│   ├── API.md                      # REST endpoint contracts & payload schemas
│   ├── ARCHITECTURE.md             # System design, LangGraph state machine, data flows
│   ├── BOOK_PROCESSING_SPEC.md     # Universal textbook parsing, heading inference & two-phase ingestion
│   ├── DATA.md                     # Vector store schemas, OpenStax data pipelines
│   ├── DESIGN.md                   # Japandi UI/UX design specifications & palette
│   ├── LOCAL_MODEL_TRAINING_GUIDE.md # LoRA / Kaggle PEFT fine-tuning & Ollama guide
│   ├── MEMORY.md                   # Working memory, conventions, and quick facts
│   └── SETUP.md                    # Detailed developer onboarding & setup guide
├── backend/                        # Python backend service
│   ├── app.py                      # FastAPI server & route handlers
│   ├── book_structurer.py          # Document structure inference engine (TOC pruning, heading scoring)
│   ├── divide_book.py              # Two-phase textbook dividing & publishing pipeline
│   ├── pedagogical_guardrails.py   # Grade-level ceilings & off-topic information filter
│   ├── tutor_graph.py              # LangGraph multi-agent cognitive graph
│   ├── local_llm_service.py        # Local Ollama / Llama-3.2-3B offline service
│   ├── database_ingest.py          # BM25 + ChromaDB hybrid RAG pipeline
│   ├── course_manager.py           # Curriculum & custom course persistence
│   ├── material_parser.py          # Algorithmic document cleaner & document text extraction
│   ├── question_generator.py       # Single-pass theory synthesis & quiz generation engine
│   ├── fuzzy_engine.py             # Mamdani fuzzy evaluation engine
│   ├── hint_utils.py               # Answer-leak sanitization & prompt guards
│   ├── theory_repo.py              # Static curriculum banks & fallback theory
│   ├── tests/                      # Dedicated automated test suites (61/61 passed)
│   │   ├── test_book_structurer.py        # Heading scoring, TOC pruning & layout tests
│   │   ├── test_two_phase_ingestion.py    # Two-phase async ingestion & crash-recovery tests
│   │   ├── test_pedagogical_guardrails.py # Grade ceiling & deflection tests
│   │   ├── test_content_aware_qg.py       # Fact extraction & assessment tests
│   │   ├── test_theory_enhancement.py     # STEM blueprints, worked examples & equation protection
│   │   ├── test_outline_ladder.py         # Multi-rung outline ladder & TOC tests
│   │   ├── test_fuzzy_extended.py         # Comprehensive Mamdani test suite
│   │   ├── test_tier1_features.py         # SM-2 & similarity tests
│   │   ├── test_tier3_features.py         # BM25 & analytics tests
│   │   └── test_section_optimization.py   # Chapter chunking tests
│   └── data/                       # Textbooks, curriculum, and sample corpora
├── frontend/                       # React 18 + Vite + Tailwind CSS frontend
│   ├── src/
│   │   ├── components/             # Reusable UI modules (ChapterNav, CourseStudio, TheoryExplorer, etc.)
│   │   ├── App.jsx                 # Main application view & glass-box telemetry HUD
│   │   └── index.css               # Japandi theme tokens & styling
│   └── package.json
├── training/                       # Fine-tuning artifacts & Llama-3.2-3B LoRA adapters
│   ├── Modelfile                   # Optimized Ollama model specification (learning-companion)
│   └── llama3.2-3b-edu-adapter/    # Extracted PEFT adapter weights (~97 MB)
├── requirements.txt                # Curated Python backend dependencies
└── README.md
```

---

## ⚡ Quick Start

### 1. Prerequisites
- **Python:** 3.10+
- **Node.js:** 18+ and npm
- **Local Ollama (Offline Inference):** [Ollama](https://ollama.com)
  ```bash
  # Pull base Llama 3.2 3B model
  ollama pull llama3.2:3b

  # (Recommended) Build the optimized Learning Companion model
  ollama create learning-companion -f training/Modelfile
  ```
- **API Key (Optional fallback):** Google Gemini API Key in `.env` (supports `gemini-3.8-flash`):
  ```env
  GEMINI_API_KEY=your_gemini_api_key_here
  ```

### 2. Backend Setup
```powershell
# 1. Activate your virtual environment
.\venv\Scripts\activate   # Windows
# source venv/bin/activate # macOS/Linux

# 2. Install backend dependencies
pip install -r requirements.txt

# 3. Start the FastAPI server
python backend/app.py
```
> The API server starts at `http://127.0.0.1:8000` with interactive docs at `http://127.0.0.1:8000/docs`.

### 3. Frontend Setup
In a new terminal window:
```powershell
cd frontend
npm install
npm run dev
```
> The web application will launch at `http://localhost:5173`.

---

## 🧪 Testing & Quality Assurance

Run the complete automated test suite across all 61 unit and integration tests:

```powershell
pytest backend/tests/ -v
```

All 61 tests verify:
- Universal book structure inference, running-header suppression, and TOC front-matter pruning (`test_book_structurer.py`, `test_outline_ladder.py`).
- Two-phase ingestion with instant skeleton publication and background enrichment (`test_two_phase_ingestion.py`).
- Grounded STEM theory generation, full worked problem extraction, and formula safeguards (`test_theory_enhancement.py`).
- Grade-level ceiling enforcement (Class 9 vs Class 12).
- Off-topic deflection guardrails.
- Primary course material grounding.
- Mamdani fuzzy logic evaluation.
- SM-2 spaced repetition intervals.
- BM25 hybrid ranking & chapter isolation.

---

## 📚 Detailed Documentation

- 🏛️ **[System Architecture](docs/ARCHITECTURE.md)**: LangGraph state machine, pedagogical guardrails, and hybrid retrieval.
- 📖 **[Book Processing Specification](docs/BOOK_PROCESSING_SPEC.md)**: Universal layout inference, TOC deduplication, and two-phase course publisher.
- 🔌 **[API Reference](docs/API.md)**: Request/response schemas for `/api/tutor/*` and `/api/material/*`.
- 🎨 **[Design System](docs/DESIGN.md)**: Japandi aesthetics, color tokens, telemetry badges, and layout guidelines.
- 🗄️ **[Knowledge Base & RAG](docs/DATA.md)**: ChromaDB vector collections, chunking, and deduplication.
- 🧠 **[Developer Memory](docs/MEMORY.md)**: Architectural gotchas, key design decisions, and system constraints.
- 🛠️ **[Environment Setup](docs/SETUP.md)**: In-depth setup, troubleshooting, and vector DB regeneration.
- 🤖 **[Local Model Training Guide](docs/LOCAL_MODEL_TRAINING_GUIDE.md)**: Kaggle PEFT fine-tuning script, adapter weights, and Ollama serving.

---

## 📄 License
Academic and research usage. See respective course material licenses for OpenStax text assets.

