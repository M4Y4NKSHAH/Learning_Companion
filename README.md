# 🧠 Learning Companion (AURA)

> **Glass-Box Multi-Agent Socratic Tutoring Platform**  
> Powered by FastAPI, LangGraph, Google Gemini, ChromaDB, and React (Japandi Design System).

---

## 📖 Overview

**Learning Companion** is an intelligent, transparent educational platform designed to foster deep understanding through Socratic inquiry rather than passive answer retrieval.

Unlike traditional "black-box" LLM tutors, Learning Companion exposes its reasoning and cognitive routing in real-time through a **Glass-Box UI**:
- **Cognitive Routing Telemetry:** Watch the agent switch between *Surface Hinting*, *Deep Decomposition*, and *Direct Instruction*.
- **Mamdani Fuzzy Inference System:** Multi-parameter evaluation that dynamically computes student mastery, error severity, response latency, and monotonic hint penalties.
- **Textbook-Grounded RAG:** Ingests OpenStax textbooks and custom course materials into ChromaDB for factual, hallucination-free guidance.
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
       +----------------------------+----------------------------+
       |                            |                            |
+------v------+              +------v------+              +------v------+
| LangGraph   |              | Mamdani     |              | ChromaDB    |
| State       |              | Fuzzy       |              | Vector RAG  |
| Machine     |              | Engine      |              | Storage     |
+-------------+              +-------------+              +-------------+
```

---

## 📁 Repository Structure

```text
Learning_Companion/
├── docs/                           # Comprehensive technical documentation
│   ├── API.md                      # REST endpoint contracts & payload schemas
│   ├── ARCHITECTURE.md             # System design, LangGraph state machine, data flows
│   ├── DATA.md                     # Vector store schemas, OpenStax data pipelines
│   ├── DESIGN.md                   # Japandi UI/UX design specifications & palette
│   ├── LOCAL_MODEL_TRAINING_GUIDE.md # LoRA / Unsloth fine-tuning guide
│   ├── MEMORY.md                   # Working memory, conventions, and quick facts
│   └── SETUP.md                    # Detailed developer onboarding & setup guide
├── backend/                        # Python backend service
│   ├── app.py                      # FastAPI server & route handlers
│   ├── analytics.py                # Guided vs. direct pathway analytics
│   ├── course_manager.py           # Curriculum & course lifecycle manager
│   ├── database_ingest.py          # ChromaDB ingestion pipeline
│   ├── flashcard_builder.py        # Algorithmic & AI flashcard generation
│   ├── fuzzy_engine.py             # Mamdani fuzzy evaluation engine
│   ├── hint_utils.py               # Answer-leak sanitization & prompt guards
│   ├── local_llm_service.py        # Local Ollama / vLLM fallback service
│   ├── material_parser.py          # Document parsing (PDF, Markdown, Text)
│   ├── question_generator.py       # Automated quiz generation engine
│   ├── theory_repo.py              # Static curriculum banks & fallback theory
│   ├── tutor_graph.py              # LangGraph multi-agent cognitive graph
│   ├── scripts/                    # Utility & terminal CLI tools
│   │   └── evaluate_cli.py         # Interactive terminal fuzzy evaluator
│   ├── tests/                      # Dedicated automated test suites
│   │   ├── __init__.py
│   │   ├── test_10_scenarios.py    # Benchmark matrix fuzzy grading tests
│   │   ├── test_fuzzy_extended.py  # Comprehensive Mamdani test suite
│   │   ├── test_ingestion_pipeline.py # RAG ingestion pipeline test
│   │   └── test_tutor_hints.py     # E2E API hint routing test
│   └── data/                       # Textbooks, curriculum, and sample corpora
├── frontend/                       # React 18 + Vite + Tailwind CSS frontend
│   ├── src/
│   │   ├── components/             # Reusable UI modules (CourseStudio, TheoryExplorer, etc.)
│   │   ├── App.jsx                 # Main application view & glass-box telemetry HUD
│   │   └── index.css               # Japandi theme tokens & styling
│   └── package.json
├── training/                       # Fine-tuning scripts (Llama-3.2 Unsloth Colab)
├── requirements.txt                # Curated Python backend dependencies
└── README.md
```

---

## ⚡ Quick Start

### 1. Prerequisites
- **Python:** 3.10+
- **Node.js:** 18+ and npm
- **API Key:** Google Gemini API Key

Create a `.env` file in the project root:
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
> The API server will start at `http://127.0.0.1:8000` with interactive docs at `http://127.0.0.1:8000/docs`.

### 3. Frontend Setup
In a new terminal window:
```powershell
cd frontend
npm install
npm run dev
```
> The web application will launch at `http://localhost:5173`.

---

## 🧪 Testing & Utilities

Run the automated test suites using Python:

```powershell
# Run the Mamdani Fuzzy Marking benchmark suite
python backend/tests/test_fuzzy_extended.py

# Run the 10-scenario calibration test
python backend/tests/test_10_scenarios.py

# Run interactive CLI evaluation tool
python backend/scripts/evaluate_cli.py
```

---

## 📚 Detailed Documentation

Dive deeper into specific subsystems:

- 🏛️ **[System Architecture](docs/ARCHITECTURE.md)**: LangGraph state machine, cognitive transitions, and component contracts.
- 🔌 **[API Reference](docs/API.md)**: Request/response schemas for `/api/tutor/*` and `/api/materials/*`.
- 🎨 **[Design System](docs/DESIGN.md)**: Japandi aesthetics, color tokens, and layout guidelines.
- 🗄️ **[Knowledge Base & RAG](docs/DATA.md)**: ChromaDB vector collections, chunking, and deduplication.
- 🧠 **[Developer Memory](docs/MEMORY.md)**: Architectural gotchas, key design decisions, and system constraints.
- 🛠️ **[Environment Setup](docs/SETUP.md)**: In-depth setup, troubleshooting, and vector DB regeneration.
- 🤖 **[Local Model Training](docs/LOCAL_MODEL_TRAINING_GUIDE.md)**: Instructions for training custom local tutor models.

---

## 📄 License
Academic and research usage. See respective course material licenses for OpenStax text assets.
