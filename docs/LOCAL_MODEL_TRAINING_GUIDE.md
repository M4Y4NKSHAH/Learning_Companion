# Local Offline Model Training & Serving Guide (Zero Token Depletion)

> **Goal**: Train **Llama-3.2-3B-Instruct** online (e.g. Google Colab / Kaggle free GPUs) and run it locally in 4-bit quantization using ~2.5 GB RAM/VRAM so the system can ingest, summarize, and generate flashcards and questions completely offline with zero cloud API token costs.

---

## 1. Why `Llama-3.2-3B-Instruct`?

- **Size**: 3.21 Billion parameters (native 128k context window).
- **VRAM footprint in 4-bit (GGUF `q4_k_m`)**: Only **~2.2 GB VRAM / RAM**.
- **Inference Speed**: ~45–60 tokens/second on an RTX 3050/3060 or fast Apple Silicon/CPU.
- **Instruct Following**: Exceptional structured JSON output capabilities.

---

## 2. Handling Massive 1,000 to 10,000-Page Books (Appendix & Clutter Separation)

When ingesting a 1,000 to 10,000-page textbook, over 30% of the pages consist of non-theory clutter:
- **Front-Matter**: Title pages, copyright, dedication, preface, Table of Contents.
- **Back-Matter**: Appendix A–Z (conversion factors, mathematical tables), solutions to odd-numbered problems, glossaries, references, index.
- **Page Noise**: Running headers, footers, page numbering.

### The 2-Tier Hierarchical Extraction Strategy

```
[ 10,000-Page Massive Book / PDF Stream ]
                 │
                 ▼
┌───────────────────────────────────────────────────────────┐
│ Tier 1: Algorithmic Boundary Slicer (material_parser.py)  │
│ • Detects Table of Contents (TOC) & Chapter Starts        │
│ • Prunes Front-Matter (Preface, Copyright, Dedication)    │
│ • Prunes Back-Matter (Appendixes, Solutions, Index)       │
│ • Strips running page headers and artifact footers        │
└───────────────────────────────────────────────────────────┘
                 │
                 ▼ (Cleaned Chapter Slices)
┌───────────────────────────────────────────────────────────┐
│ Tier 2: Fine-Tuned Llama-3.2-3B Section Classifier        │
│ • Reads chapter text via 128k context window              │
│ • Labels section: [CORE_THEORY] vs [APPENDIX_DATA]        │
│ • Rejects appendix tables & non-instructional text        │
│ • Synthesizes 3 High-Impact Flashcards & Objectives       │
└───────────────────────────────────────────────────────────┘
```

---

## 3. Curated Open-Source Datasets for Theory & Layout Separation

| Dataset | Hugging Face ID | Size | Purpose |
| --- | --- | --- | --- |
| **DocBank / PubTables-1M** | `docbank` / `pubtables-1m` | 500k pages | Fine-grained document layout labels (separates body text from tables, appendixes, and footnotes) |
| **ArXiv Summarization** | `ccdv/arxiv-summarization` | 215k docs | Dense academic paper & research article chapter summaries |
| **BookSum (Chapter-Level)** | `kmfoda/booksum` | 40k chapters | Long-form multi-chapter textbook summarization |
| **SciQ** | `allenai/sciq` | 13.6k QA pairs | Science concept checks with support explanations |

---

## 3. Online Training Procedure (Step-by-Step in Google Colab)

### Step 1: Open Google Colab with a Free T4 GPU
1. Go to [colab.research.google.com](https://colab.research.google.com).
2. Set Runtime -> Change runtime type -> **T4 GPU** (Free tier).

### Step 2: Run the Training Script
Upload and execute [`training/train_llama32_unsloth_colab.py`](file:///c:/Users/pc/Documents/OneDrive/Desktop/Learning_Companion/training/train_llama32_unsloth_colab.py).

```python
# Installs 5x faster QLoRA engine
!pip install "unsloth[colab-new] @ git+https://github.com/unslothai/unsloth.git"
!pip install --no-deps "xformers<0.0.29" "trl<0.9.0" peft accelerate bitsandbytes datasets
```

The script will:
1. Load `unsloth/Llama-3.2-3B-Instruct` in 4-bit precision.
2. Attach LoRA adapters to attention projection layers (`q_proj`, `k_proj`, `v_proj`, `o_proj`).
3. Train for 120 steps (~1.5 hours) on academic chapter-to-flashcard JSON pairs.
4. Auto-export the fine-tuned model into `llama3.2-3b-edu-Q4_K_M.gguf`.

---

## 4. Serving Locally in 1 Minute via Ollama

Once `llama3.2-3b-edu-Q4_K_M.gguf` is downloaded to your PC:

### Option A: Using Ollama (Recommended)
1. Install [Ollama](https://ollama.com) on Windows.
2. In your model folder, create a `Modelfile`:
   ```dockerfile
   FROM ./llama3.2-3b-edu-Q4_K_M.gguf
   TEMPLATE """<|begin_of_text|><|start_header_id|>system<|end_header_id|>
   {{ .System }}<|eot_id|><|start_header_id|>user<|end_header_id|>
   {{ .Prompt }}<|eot_id|><|start_header_id|>assistant<|end_header_id|>
   {{ .Response }}<|eot_id|>"""
   PARAMETER temperature 0.3
   PARAMETER num_ctx 4096
   ```
3. Register and run the model:
   ```bash
   ollama create llama3.2:3b -f Modelfile
   ollama run llama3.2:3b
   ```

### Option B: Using Base Ollama Llama-3.2 Directly (Zero Setup)
You can also run the official pre-trained Llama 3.2 model immediately:
```bash
ollama run llama3.2:3b
```

---

## 5. Automatic Backend Detection

Our backend [`backend/local_llm_service.py`](file:///c:/Users/pc/Documents/OneDrive/Desktop/Learning_Companion/backend/local_llm_service.py) automatically polls `http://localhost:11434`:
- When Ollama is running, it will automatically serve local summarization and flashcard synthesis.
- If cloud Gemini tokens are depleted or the network is disconnected, the system automatically falls back to your local `Llama-3.2-3B-Instruct` engine with zero disruption!
