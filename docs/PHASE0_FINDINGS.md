# Phase 0 Findings & Baseline Quality Investigation

**Document:** `docs/PHASE0_FINDINGS.md`  
**Target Book:** `COMPUTER_SCIENCE-compressed.pdf` (OpenStax *Introduction to Computer Science*, 939 pages)  
**Date:** 2026-10-03  

---

## 1. Baseline Test Suite Verification
- **Test Command:** `pytest backend/tests/ -q`
- **Result:** **43 passed, 0 failed** in 43.20s.
- All existing unit, integration, and guardrail tests pass cleanly.

---

## 2. Ingestion Failure on `COMPUTER_SCIENCE-compressed.pdf`

We ran the existing extraction and structuring pipeline (`backend/book_structurer.py`) on the full text of `COMPUTER_SCIENCE-compressed.pdf` (2,561,051 characters, 384,970 words).

### Output Findings
- **Real Structure (Ground Truth from embedded PDF bookmarks):**
  - **14 chapters**, exactly **61 sections**.
- **Current Pipeline Output:**
  - Winning heuristic pattern: `hash_headings` (`# ...`).
  - Chapters detected: **35 false chapters**.
  - Detected "Chapter" titles:
    - Chapter 1: `include <iostream>`
    - Chapter 2: `include <iostream>`
    - Chapter 3: `include <stdio.h> /* include printf prototype */`
    - Chapter 4: `include <stdio.h>`
    - Chapter 5: `include <stdlib.h>`
    - Chapter 6: `include <dlfcn.h>`
    - Chapter 10: `pragma omp parallel num_threads(y * 3)`
  - **Root Cause in Code:** In C/C++ code listings throughout the textbook, lines like `#include <stdio.h>` or `#pragma ...` are parsed as Markdown H1 headings (`# Heading`)! Because `hash_headings` scored 0.954 in `BookStructurer._score_candidate()`, C code preprocessor directives hijacked the entire book structure!
- The baseline result has been saved to `backend/tests/fixtures/baseline_cs_course.json`.

---

## 3. Verification of Probable Root Causes (§1)

| Root Cause Hypothesis | Code Location | Finding / Evidence |
| :--- | :--- | :--- |
| **Context Window Starvation (2% of chapter)** | `backend/question_generator.py:320`<br>`backend/question_generator.py:364`<br>`backend/question_generator.py:399`<br>`backend/local_llm_service.py:42, 191, 216` | **CONFIRMED.** `ctx = text[:2600]` in `_local_synthesize_unified()`; `_PROMPT_BUDGET = 3400` in `local_llm_service.py`. An average chapter in the CS book has **21,400 words (~140,000 characters)**. Slicing to 2,600 characters means the LLM sees **1.8% of the chapter**, starving the model of all core content. |
| **Chapter marker `^CHAPTER N$` missing** | `backend/book_structurer.py:156`<br>`backend/divide_book.py:355` | **CONFIRMED.** OpenStax CS textbook does not contain `^CHAPTER N$` or `Chapter 1: ...` on its own line in running body text. Chapters open with a bare cover figure, then `Chapter Outline`, then `1.1 Computer Science`. |
| **Running page headers contain real chapter info** | Pages 20–939 | **CONFIRMED.** Even-numbered pages have printed footers: `10     1 • Introduction to Computer Science`. The chapter number and title are printed verbatim in the running furniture on every single page. |
| **Summaries instead of Lessons** | `backend/question_generator.py:333-341` | **CONFIRMED.** Prompt demands `summary: 2-3 sentence overview`, `3 objectives`, `3 flashcards`. The result is a passive, shallow cheat sheet rather than an interactive pedagogical lesson. |
| **Layer 1 is regex templates** | `backend/question_generator.py:798-901` | **CONFIRMED.** `_build_subject_deep_theory()` uses rigid, hardcoded fallback strings ("Derived from foundational conservation and symmetry principles"). When regexes fail, every chapter gets identical copy-pasted text. |
| **Local Model Configured Too Small** | `training/Modelfile:24-25`<br>`backend/local_llm_service.py:112` | **CONFIRMED.** `num_ctx 2048` and `num_predict 800` severely throttle authoring capacity, preventing multi-step pedagogical scaffolding. |
| **Flawed LoRA Training Script** | `training/llama3.2-3b-edu-adapter`<br>`docs/LOCAL_MODEL_TRAINING_GUIDE.md:43, 84` | **CONFIRMED.** Training dataset consists of **3 unique examples multiplied by 50**. LoRA targets in the script are only 4 modules (`q_proj, k_proj, v_proj, o_proj`), whereas docs claimed all 7. The 6-file teacher-student dialogue corpus in `backend/data/dialogue/teacher_student_corpus/` was never used. |
| **Incomprehensible Evaluation & Distractor Leak** | `backend/question_generator.py:1129-1145`<br>`backend/hint_utils.py:11` | **CONFIRMED.** In `generate_assessment_items()`, `options = [correct] + distractors[:3]` without random shuffling. **The correct answer is Option A 100% of the time in fallback mode!** Moreover, latency is factored into fuzzy score, penalizing students who take time to reflect. |

---

## 4. Scope Guardrail Test (`pedagogical_guardrails.OFF_TOPIC_PATTERNS`)

We tested `OFF_TOPIC_PATTERNS` against legitimate computer science topics that are actually covered in the book:
- `explain bitcoin proof of work`: **BLOCKED!** Matched regex `\b(...|crypto|bitcoin|buy doge|casino|betting tips)\b`.
- We scanned `COMPUTER_SCIENCE-compressed.pdf` across all 939 pages:
  - `blockchain`: Found on **58 pages** (e.g. Section 11.6: *"Sample Ethereum Blockchain Web 2.0/Web 3.0 Application"*, pages 647–659).
  - `crypto`: Found on **36 pages** (cryptography, cryptographic hash functions, public-key encryption).
  - `bitcoin`: Found on **5 pages** (pages 406, 586, 789, 790, 857).
  - `malware`: Found on **11 pages** (Chapter 14 Cybersecurity).
  - `ddos`: Found on **4 pages** (denial of service attacks in cybersecurity).

**Conclusion:** The regex pattern `\b(crypto|bitcoin)\b` immediately triggers an off-topic deflection on authentic, core textbook material! A student asking about Section 11.6 will be falsely told that the topic is outside the curriculum.

---

## 5. Review Questions & Answer Key Verification
- We searched all 939 pages for `"Answer Key"`, `"Answers to"`, `"Solutions to"`.
- Found on page 13: Preface describes pedagogical features and mentions student review questions.
- Scanned the entire back matter (pages 839 to 939).
- **Result:** **No Answer Key exists in the textbook for the Review Questions.**
- The book contains rich Review Questions at the end of every chapter (e.g., page 45 has 18 Review Questions for Chapter 1), but answers are withheld (standard for college textbooks).
- **Impact for Phase 4:** The assessment import pipeline must have the model propose answers with citations back to the source text (`answer_status: "model_proposed"` with `answer_confidence`), and unverified answers must never be graded as absolute truths without verification against source text.

---

## 6. Repository Document Inconsistencies Resolved

1. **LLM Call Order:**
   - In `question_generator.py:201`: Local LLM is checked first. If unavailable, falls back to Gemini (`allow_cloud_fallback`), then deterministic fallback.
   - In `tutor_graph.py:257`: Local LLM checked first, then Gemini, then curated rule matrix.
   - `ARCHITECTURE.md` is correct; `MEMORY.md` was outdated and will be revised.
2. **ChromaDB Folders:**
   - Root `chroma_knowledge_base/` has stale folders from September 23, 2026.
   - `backend/chroma_knowledge_base/` is the active, live directory where `backend/database_ingest.py` reads/writes (`chroma.sqlite3` is 11.1 MB, last modified today). Root folder can be cleaned up in Phase 7.
3. **Academic Tiers & Subject Hardcoding:**
   - Code allows `"Standard"` as default, whereas documentation specified `"Class 10"`, `"Class 11-12"`, `"Undergraduate"`.
   - `question_generator.py:807-885` and `divide_book.py` had hardcoded branch logic for physics, math, and bio; computer science fell back to generic placeholders.
