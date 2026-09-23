# 📚 Data & Knowledge Base — Learning Companion

> Everything the tutor "knows", where it lives, and how it flows. Two kinds of knowledge:
> **(1)** the static question bank (`theory_repo.py`) and **(2)** the dynamic RAG vector
> store built from OpenStax textbooks (`chroma_knowledge_base` → `curriculum_repository`).

---

## 1. Data Directory Map

```
project_root/
├─ chroma_knowledge_base/          # ★ LIVE ChromaDB where the pipeline writes
│  ├─ chroma.sqlite3               #    (collection index + metadata)
│  └─ <collection_id>/*.bin        #    (embedding/vector shards)
├─ backend/
│  ├─ chroma_knowledge_base/       # ⚠️ STALE leftover copy — NOT used. Safe to delete.
│  ├─ data/
│  │  ├─ curriculum/               # OpenStax textbook plain-text sources
│  │  │  ├─ physics_textbook.txt
│  │  │  ├─ biology_textbook.txt
│  │  │  ├─ math_textbook.txt
│  │  │  └─ calculus_textbook.txt
│  │  ├─ ednet/
│  │  │  ├─ ednet_small_sample.csv # behavioral interaction telemetry sample
│  │  │  └─ shrink_dataset.py      # script that produced the sample
│  │  └─ dialogue/
│  │     └─ teacher_student_corpus/
│  │        ├─ conversations_train1..5.json
│  │        ├─ conversations_eval.json
│  │        └─ README.md
│  └─ theory_repo.py               # static flashcard/quiz/exam repository (python)
└─ frontend/src/App.jsx            # FALLBACK_CURRICULUM (offline copy of the deck)
```

---

## 2. Static Question Bank — `theory_repo.py`

A pure-Python nested dict: `FLASHCARD_REPOSITORY[subject][tier]`.

| Subject | Tiers | Contents per tier |
| --- | --- | --- |
| Physics | Class 10, Class 11-12, Undergraduate | `cards[3]`, `quizzes`, `finalExam[]` |
| Biology | Class 10, Class 11-12, Undergraduate | same shape |
| Mathematics | Class 10, Class 11-12, Undergraduate | same shape |

**Card schema**

```jsonc
{ "id": "p10_c1", "topic": "Newton's Second Law",
  "question": "…", "answer": "• Key bullet 1\n• Key bullet 2\n• Key bullet 3" }
```

**Final-exam question schema** (used by short-answer grading & exam evaluation)

```jsonc
{ "qId": "p10_f1",
  "moduleOrigin": "Module 1: Newton's Second Law",
  "text": "A mechanical component … Compute the total active horizontal force …",
  "expected": "32",
  "formula": "Force = Mass x Acceleration (F = m x a)",
  "misconception": "Student might be dividing the variables (8/4 or 4/8)…" }
```

Card ID prefix convention: `p` → Physics, `b` → Biology, `m` → Mathematics, then tier
slug (`10`, `12`, `ug`) — e.g. `b12_c2`, `mug_f1`.

---

## 3. RAG Vector Store — ChromaDB

**Pipeline:** `backend/database_ingest.py` → `DatabaseIngestPipeline`.

| Property | Value |
| --- | --- |
| Client | `chromadb.PersistentClient(path=<root>/chroma_knowledge_base)` |
| Collection | `curriculum_repository` |
| Embeddings | Chroma `DefaultEmbeddingFunction` |
| Chunking | split on `\n\n` (paragraphs), keep only `len(strip) > 40` |
| Batch size | 2000 docs per `add()` call |
| Document ID | `<subject>_<tier_slug>_<4-digit index>` |
| Metadata | `{ subject, academic_tier, grade_level, data_integrity_status: "verified" }` |

**Textbook → collection mapping** (defined in `database_ingest.py` `__main__`)

| Source file | Subject | Tiers loaded |
| --- | --- | --- |
| `physics_textbook.txt` | Physics | Class 10, Class 11-12, Undergraduate |
| `biology_textbook.txt` | Biology | Class 10, Class 11-12, Undergraduate |
| `math_textbook.txt` | Mathematics | Class 10, Class 11-12 |
| `calculus_textbook.txt` | Mathematics | Undergraduate |

**Queries** filter by `{"$and": [{academic_tier}, {subject}]}` with `n_results=3` (chat
and RAG factory) or `n_results=12` (flashcard builder).

**Lifecycle:** running `python backend/database_ingest.py` **deletes** the old
`curriculum_repository` and re-embeds everything. The vector DB persists on disk between
server restarts; ingestion is only required when adding new sources.

> ⚠️ **Duplicate DB gotcha:** `backend/chroma_knowledge_base/` also exists in the repo but
> `database_ingest.py` always resolves the data path to the **project root**
> (`base_dir = os.path.dirname(os.path.dirname(__file__))`). The `backend/` copy is stale
> and can be removed.
---

## 4. Flashcard Generation — Two Mechanisms (`flashcard_builder.py`)

### Heuristic path — `build_flashcards_from_chroma(subject, tier, max_cards=3)`
1. Query Chroma `n_results=12` for `"<subject> core concepts <tier>"`.
2. Filter chunks with `_is_educational_content` (length 90–1400, no OpenStax boilerplate
   words, alpha-ratio > 0.55).
3. Extract a topic per chunk via `_extract_topic` (regex: definition sentences
   `"… is/are/refers to …"`, heading-style match, else first 72 chars).
4. Format answer as `• bullet` lines (`_format_answer`), dedupe topics.
5. Stable id from MD5: `ch_<subj3>_<tier>_<md5:10>`.
6. Cached in `_flashcard_cache[(subject, tier)]`.

### AI path — `generate_gemini_flashcards_from_chroma(subject, tier)`
1. Pull top-5 educational chunks from Chroma as prompt context.
2. Ask `gemini-2.5-flash` (temp 0.3) for **exactly 3** cards as a strict JSON array.
3. Parse & tag `"source": "gemini_rag"`, id `ai_<subj3>_<tier3>_<n>`.
4. On any failure → fall back to the heuristic builder.
5. Cached in `_gemini_flashcard_cache[(subject, tier)]`; returned via
   `/api/tutor/load-theory` (as `is_ai_generated=true`) and
   `/api/tutor/generate-flashcards`.

---

## 5. Behavioral & Dialogue Datasets (currently auxiliary)

- **EdNet sample** — `backend/data/ednet/ednet_small_sample.csv`
  (produced by `shrink_dataset.py`). Student interaction rows with `user_id`, action,
  `elapsed_time`. Only used by `DatabaseIngestPipeline.preview_interaction_metrics()` for
  a console preview — not yet wired into live scoring.
- **Teacher–student dialogue corpus** — `conversations_train1..5.json` +
  `conversations_eval.json` (see its own `README.md`). Example transcripts of Socratic
  teacher–student exchanges; not yet consumed by the running app — reserved for fine-tuning
  or few-shot prompting.

---

## 6. What The Tutor Actually Sees Per Turn

```
API request (subject + tier + message)
   │
   ▼
retrieve_context:  top-3 chunks from curriculum_repository (metadata-filtered)
   │
   ▼
analyze_depth:     Mamdani fuzzy score (accuracy heuristics × latency)
   │
   ▼
discussion node:   prompt = [system: grounded context + node identity]
                   [history...] + latest HumanMessage  → gemini-2.5-flash
   │
   ▼
response + telemetry (active_node, depth_level, fuzzy meta)
```

Everything displayed as `context_pulled` in the `/api/tutor/chat` response and in the
frontend "Context Metadata" panel is real retrieved text — that's how the "glass box"
shows the student *which* textbook content grounded the tutor's answer.

---

## 7. Offline Safety Net — `FALLBACK_CURRICULUM`

`App.jsx` embeds a small offline copy of the deck (Physics Class 10 + Mathematics
Undergraduate examples) so the UI renders a meaningful Study Deck even when the backend or
ChromaDB is unavailable. Data format mirrors `theory_repo.py` exactly.

---

## 8. Changing / Extending Content

| Goal | Action |
| --- | --- |
| Edit exam questions, formulas, misconceptions | `backend/theory_repo.py` |
| Add a new textbook to RAG | Add `.txt` to `backend/data/curriculum/`, register in `database_ingest.py`'s `textbooks`, run `python backend/database_ingest.py` |
| Tune flashcard filtering | `flashcard_builder.py` constants (`BOILERPLATE_KEYWORDS`, `_is_educational_content`) |
| Add another academic tier | Reference the tier string consistently in `theory_repo.py`, `database_ingest.py`, `App.jsx` tier pills, and ChromaDB metadata filters |
| Back up the vector store | Copy the whole `chroma_knowledge_base/` folder (do not copy only `chroma.sqlite3` — vector shards are needed)