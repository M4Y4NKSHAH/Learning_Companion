# 📚 Book → Course Processing Specification (v2)

> **Objective**: define an **exact, reproducible recipe** for turning a raw textbook
> file into a publishable *Learning Companion* course — correct chapters, correct
> sections, pedagogically grouped units, and source-grounded theory.
>
> The recipe works for **any book the user supplies** (PDF, EPUB, markdown, pasted
> notes) as well as the bundled OpenStax textbooks: the structure is *inferred*
> from the document, never assumed. See §2.1.
>
> This document is intentionally implementation-agnostic: it can be handed to any
> engineer, or pasted into another LLM (Gemini, GPT, Claude) to reproduce or port
> the pipeline. The reference implementation is `backend/divide_book.py` for the
> publishing engine and `backend/book_structurer.py` for structure inference.

---

## 1. Scope & Guarantees

| Guarantee | How it is enforced |
| --- | --- |
| Works on any book, not one publisher's format | Heading style, section style and units are inferred per document (`book_structurer`) |
| Chapter titles come from the book's real Table of Contents | TOC is parsed from front matter before any cutting; if absent, inferred headings become the TOC |
| No TOC entry can be mistaken for a chapter body | Front-matter listings are detected and pruned before cutting |
| Numbered equations can never become "sections" | Candidate headings are validated against the TOC section list or the detected `N.M` family |
| Running page headers can never become sections | Publisher-specific **and** frequency-inferred header/footer forms are rejected |
| Every chapter has theory, even fully offline | Deterministic skeleton is always built, LLM only enriches |
| No hallucinated formula enters a course | LLM output is grounded back against facts extracted from the source |
| A published course shows up in the app immediately | Course JSON is written through `CourseManager.save_custom_course()` |
| A book with no headings still produces a course | Size-balanced chapter/section chunking is the last fallback |

**Non-goals**: OCR of scanned PDFs, image/figure extraction, two-column
de-interleaving of boxed summary panels, and mathematical symbol recovery when the
source text has lost the symbols.

---

## 2. Inputs

| Input | Requirement |
| --- | --- |
| Source | A file path (`--file`, any of `.txt`, `.md`, `.pdf`, `.epub`, `.mobi`, `.xps`, `.fb2`) **or** raw text passed to `SmartBookDivider(text=...)` **or** a bundled preset key (`--source physics|math|calculus|biology`) |
| Metadata | Title (defaults to a prettified filename), subject, academic tier, optional explicit `course_id` |
| Page markers | Optional (`--- Page N ---`); stripped when present |
| Chapter markers | Anything the inference layer scores best (see §2.1) |
| Section markers | Anything the inference layer scores best, else size-balanced chunks |
| Book registry | Optional preset entries in `BOOKS` (`backend/divide_book.py`): `path`, `title`, `subject`, `tier`, `units`, `course_id` |

### 2.1 Structure inference (what makes this work for *any* book)

`BookStructurer(text).plan()` returns a `StructurePlan` describing the document:

| Field | Meaning |
| --- | --- |
| `chapter_kind` | Winning heading family: `chapter_digits`, `chapter_roman`, `chapter_word`, `unit_*`, `lesson_digits`, `hash_headings`, `numbered_dot`, `numbered_bare`, `titled_caps`, `none` |
| `chapter_matches` | `HeadingSpot(pos, number, title, line, level)` list — one per real chapter, front-matter listings pruned |
| `section_kind` / `section_level` | `numdot`, `numdot_deep`, `dashdot`, `letdot`, `shortline`, `hash_headings`, or `chunk` |
| `units` / `unit_kind` | Declared `PART/UNIT/MODULE` ranges, or `None` → balanced buckets |
| `body_start` | Char offset where running text begins (TOC skipped) |
| `running_forms` | Digit-normalised line shapes repeated 5+ times → suppressed as running headers |
| `confidence`, `notes` | Human-readable explanation of every decision |

Candidate patterns are scored with weighted signals — sequence quality, document
spread, heading quality (short line, real title), population, and a
specificity bonus — so a generic pattern can never hijack a book that numbers its
chapters. Chapter regexes run **first** and *claim* their lines; unnumbered
patterns (`#` headings, ALL-CAPS lines) only see the remaining lines.

Front-matter detection is layout-based: consecutive headings are clustered by gap
size and the largest relative gap jump separates "TOC listing" spacing from
"chapter" spacing. A listing run of 3+ headings is pruned, *except* where no
running-text copy exists (books whose body repeats no markers). This is what keeps
three stacked listings (contents, brief contents, chapter start) from becoming 102
chapters.

Degradation ladder for sections: validated `N.M` → other heading families →
size-balanced chunks. For chapters: detected pattern → balanced "parts" (never an
exception).


Bundled sources live in `backend/data/curriculum/`:

| Key | File | Chapters |
| --- | --- | --- |
| `physics` | `physics_textbook.txt` | 34 |
| `math` | `math_textbook.txt` | OpenStax *Algebra & Trigonometry* |
| `calculus` | `calculus_textbook.txt` | OpenStax *Calculus* |
| `biology` | `biology_textbook.txt` | OpenStax *Biology 2e* |

---

## 3. Pipeline Overview

```
raw .txt
  │
  ├─ Stage 1  Split front matter (cover/TOC/preface) from running text
  │
  ├─ Stage 2  Parse the TOC  ──────────────► [{chapter, title, sections[], page}]
  │
  ├─ Stage 3  Locate chapter bodies  ──────► [{chapter, start, end}]
  │
  ├─ Stage 4  Split each chapter body ─────► intro + N.M sections + review
  │
  ├─ Stage 5  Group chapters into units ───► pedagogically coherent unit map
  │
  ├─ Stage 6  Synthesize theory ───────────► deterministic skeleton (+ Llama JSON enrichment)
  │
  └─ Stage 7  Publish course JSON ─────────► backend/data/courses/<course_id>.json
```

Each stage is **independently testable**; run the CLI with `--max-chapters 2` for a
fast end-to-end smoke test.

---

## 4. Stage 1 — Front Matter vs. Running Text

PDF text dumps of textbooks start with cover/license/preface/TOC. A chapter must
**never** be cut inside that region.

**Rule**: find every line matching `^CHAPTER\s+(\d{1,3})$` (call them *markers*).
The running text begins at the **second occurrence of `CHAPTER 1`** — the first one
belongs to the TOC.

```
markers     = [(pos, num) for every ^CHAPTER N$ line]
body_start  = position of the 2nd marker whose num == 1
toc_region  = raw_text[:body_start]
body_region = raw_text[body_start:]
```

**Fallbacks** (books that number chapters unusually):
1. First `CHAPTER 1` marker that is not the very first marker.
2. Single marker → that marker.
3. Several markers, none equal to 1 → the middle marker.

Then, inside `toc_region`, discard everything before the word `contents` when it
exists, so the cover page and licence blurb cannot inject phantom chapters.

*Reference result for `physics_textbook.txt`: `body_start = 40688` of 4,117,220 chars.*

---

## 5. Stage 2 — Table of Contents Parsing

Iterate the lines of `toc_region` with a tiny state machine:

| Line seen | Action |
| --- | --- |
| `CHAPTER N` | Open a new chapter record; start collecting its title words |
| `N.M <Title> <Page>` where `N` == current chapter | Append `{label: "N.M", title: "<Title>"}` |
| Any other text line while the title is still incomplete | Append to the title buffer (handles wrapped titles) |
| A title buffer with a trailing page number | Finalize `title` and `page` |

**Key rules**

1. **Multi-line titles**: `"Further Applications of Newton's Laws: Friction, Drag, and\nElasticity 199"` → one title, joined with a single space.
2. **Strip trailing page numbers** (`\s+\d{1,4}$`) from every title.
3. Section labels are only accepted when their chapter prefix matches the current
   chapter (prevents `12.1` inside chapter 3).
4. A chapter survives only if it has **both** a title **and** at least one section.

**Reference result**: 34 chapters, 244 sections.

---

## 6. Stage 3 — Chapter Body Localisation

Within `body_region`, walk the markers in order and build boundaries:

```
for each marker i with number N:
    skip N if it was already seen        # duplicate markers never split a chapter
    start = marker position
    end   = position of marker i+1 (or EOF)
sort boundaries by start
recompute ends: boundary[i].end = boundary[i+1].start
```

**Why "skip already seen" matters**: some dumps repeat chapter headings inside
running headers, which would otherwise create dozens of 6-character "chapters".

**Fallback** (`_section_anchor_fallback`) for books without `CHAPTER N` in the body:
anchor each chapter on the *first* section label of its TOC entry
(`^N.M\s+[A-Z]`), keeping the first hit after `body_start`.

**Rejection**: any candidate chapter whose cleaned body is shorter than 500 chars
is dropped (it is front matter or an index page, not a chapter).

*Reference result: 34 chapter bodies located.*

---


## 7. Stage 4 — Section Splitting (the part that usually goes wrong)

Per chapter body: `intro → N.M sections → review`.

### 7.1 Find the in-chapter outline block

Bodies open with `CHAPTER OUTLINE` followed by the chapter's section list. Those
lines look exactly like real headings, so they must be skipped:

```
if a line equals "CHAPTER OUTLINE":
    advance past every following line matching N.M <Title> (blank lines allowed)
    search_from = first line after that block
```

If there is no outline marker, search from the top of the body.

### 7.2 Accept only TOC-validated headings

A candidate line is a real section heading **iff all** of these hold:

1. It starts at the beginning of a line: `^(\d{1,3})\.(\d{1,3})\s+(.+)$`
2. Its chapter prefix equals the current chapter number
3. `label` is present in the chapter's TOC section list
4. `label` has not been used yet (first occurrence wins)
5. It contains **no** page-header separator glyph (`•`, `·`)
6. It is **≤ 110 characters** long (longer lines are prose, not headings)
7. The remaining title has ≥ 3 chars and at least 3 letters

Sorted accepted positions = section start indexes.

### 7.3 Reject noise

Four patterns kill the header/footer artefacts PDF extraction produces:

```python
PAGE_HEADER_RE   = ^\d{1,3}\.\d{1,3}\s*[•·ò]\s+.+\s\d{1,4}$   # "1.1 • Physics: An Introduction 9"
PAGE_HEADER_RE_2 = ^\d{1,4}\s+\d{1,3}\s*[•·ò]\s                # "138  3 • Section Summary"
FOOTER_RE        = Access for free at openstax.org | This OpenStax book is available for free | ...
PAGE_MARK_RE     = ^---\s*Page \d+\s*---$
```

> ⚠️ **The bullet-glyph trap.** The extracted bullet is Unicode `U+2022 (•)`, and it
> doubles as the separator in running headers. Dropping every line containing it
> deletes the chapter's `LEARNING OBJECTIVES`; keeping every such line floods
> sections with page headers. The fix: treat whole-line **patterns** as noise, and
> *normalise* a leading bullet to `- ` everywhere else.

### 7.4 Heading line with glued prose

`"3.3 Vector Addition and Subtraction: Analytical Methods The analytical method…"`
(previous page's last line and the heading run together). Rule: after matching
`label + TOC title` at the start of the accepted heading line, keep the **remainder**
as the first line of that section's content.

### 7.5 Section assembly

| Section | Range | Rules |
| --- | --- | --- |
| `N.0 Introduction` | body start → first heading (or review) | drops outline/heading lines, needs > 120 chars |
| `N.M <TOC title>` | heading → next heading (or review) | content = remainder + following lines, needs ≥ 80 chars |
| `N.r Glossary, Summary & Exercises` | first line matching `Glossary / Section Summary / Summary / Conceptual Questions / Problems & Exercises / Exercises / Key Terms / Chapter Review` → end | needs > 200 chars |

The review cut applies to **all** ranges, so the last numbered section never
swallows the glossary.

**Cleaning pass** on every section: drop noise lines, collapse 3+ newlines, convert
leading bullets to `- `, squeeze double spaces (symbols rendered as images leave
empty gaps).

*Reference result: 312 sections across 34 chapters (~9 per chapter).*

---


## 8. Stage 5 — Unit Grouping

Chapters are grouped into **study units** so the UI can present a syllabus instead
of a 34-item flat list.

1. If the book declares an explicit map (`units` in `BOOKS`, e.g. `PHYSICS_UNITS`),
   use it:
   ```python
   {"unit": 1, "name": "Foundations & Mechanics", "chapters": list(range(1, 11))}
   ```
2. Otherwise fall back to balanced buckets of 7: `unit_index = (chapter - 1) // 7 + 1`.

| Unit | Name | Chapters |
| --- | --- | --- |
| 1 | Foundations & Mechanics | 1–10 |
| 2 | Fluids & Thermodynamics | 11–15 |
| 3 | Oscillations, Waves & Sound | 16–17 |
| 4 | Electricity & Magnetism | 18–24 |
| 5 | Optics & Light | 25–27 |
| 6 | Modern Physics & Frontiers | 28–34 |

Every chapter carries `unit_index` + `unit_name`; the course also stores a
`units` array so the frontend can render the syllabus without recomputing.

---

## 9. Stage 6 — Theory Synthesis

Theory is produced in **two layers**, so a course is never empty and never wrong.

### 9.1 Layer 1 — deterministic grounded skeleton (always)

Built from the chapter's own text, offline and instantly:

| Produced | Source |
| --- | --- |
| `facts` | regex extraction of definitions, equations, constants |
| `key_terms` | term/definition pairs, cleaned by `_clean_concept()` |
| `worked_examples` | short solved-problem snippets copied verbatim |
| `deep_theory` skeleton | `principles`, `formulations`, `mental_models`, `misconceptions` |
| `cards` | `_facts_to_cards()` when no LLM cards are available |
| `summary` / `objectives` | template synthesis from the extracted facts |

**Concept hygiene** (guards against junk like `"ntributed to the formation"`):
concepts must start with a capital letter, contain ≤ 6 words and ≤ 60 chars, must be
preceded by a non-letter, and may neither start nor end with a stop word
(`the, and, of, what, is, …`).

### 9.2 Layer 2 — local Llama enrichment (`--llm`)

Two small, decomposed JSON-mode calls against Ollama (model resolution order:
`learning-companion` → `llama3.2:3b`).

**Phase A — blueprint** (`temperature 0.2`, `max_tokens 1200`, chapter context 2800 chars):

```json
{
  "summary": "2-3 sentence rigorous synthesis of the governing principles",
  "objectives": ["3 distinct learning objectives"],
  "principles":   [{"title": "name", "content": "definition/axiom", "tag": "Core Axiom|Law|Definition"}],
  "formulations": [{"title": "name", "formula": "equation", "derivation": "how it follows", "variables": "symbol meanings"}],
  "mental_models": [{"concept": "name", "analogy": "everyday analogy", "takeaway": "one-sentence insight"}],
  "misconceptions": [{"trap": "common student error", "correction": "why it is wrong"}]
}
```

**Phase B — cards** (`temperature 0.2`, `max_tokens 1000`, context 2400 chars): 3
cards with `topic` / `question` / `answer`, answers using the bullet template
`• Core Principle / • Governing Rule / • Application`. If the 3B model fails to
return valid JSON, one **simplified retry** runs (flat schema, `temperature 0.1`),
then a single-sentence paraphrase schema.

### 9.3 Grounding & merge

The LLM output is never trusted blindly:

* Arrays from the LLM are coerced item-by-item; items failing shape validation are
  replaced from the deterministic skeleton.
* Formulas are kept only when their symbols appear in the chapter's extracted facts.
* `key_terms` and `worked_examples` **always** come from the source text.
* Everything passes grade-level guardrails (`get_grade_level_guardrails(tier)`).

### 9.4 Cost model

| Mode | Wall-clock (RTX-class laptop, 3B Q4) | When to use |
| --- | --- | --- |
| deterministic | ~1 s / chapter | CI, offline machines, bulk smoke tests |
| `--llm` | ~30 s / chapter (~17 min for 34 chapters) | final course build |
| `--llm --max-chapters N` | N × 30 s | produce a partially enriched course now, enrich the rest later |

Because enrichment is per-chapter and the deterministic skeleton is always the
safety net, a partially enriched course is still fully usable.

---


## 10. Stage 7 — Publishing

`publish()` builds the course dictionary and calls
`CourseManager.save_custom_course(course)`, which writes
`backend/data/courses/<course_id>.json` (pretty-printed, UTF-8, `is_builtin=false`).
`CourseManager.list_all_courses()` picks the file up immediately, so the course
appears in the Course Studio with no server restart.

### 10.1 Course JSON schema

```jsonc
{
  "course_id": "custom_phy_college_physics_2e",
  "title": "College Physics 2e (OpenStax)",
  "subject": "Physics",
  "academic_tier": "Undergraduate",
  "is_builtin": false,
  "source_book": "physics_textbook.txt",
  "description": "Complete division of ... into 34 chapters grouped into 6 study units.",
  "chapters_count": 34,
  "sections_count": 312,
  "unit_count": 6,
  "units": [{ "unit_index": 1, "unit_name": "Foundations & Mechanics" }],
  "flashcards_count": 64,
  "quizzes_count": 0,
  "exam_questions_count": 0,
  "chapters": [
    {
      "chapter_id": "ch_4",
      "chapter_index": 4,
      "title": "4. Dynamics: Force and Newton's Laws of Motion",
      "unit_index": 1,
      "unit_name": "Foundations & Mechanics",
      "toc_sections": ["4.1", "4.2", "..."],
      "sections_count": 10,
      "subsections": [{ "section_id": "sec_4_4_2", "label": "4.2", "title": "Newton's First Law of Motion: Inertia" }],
      "content_preview": "CHAPTER 4 Two-Dimensional ...",
      "full_text": "<cleaned chapter text>",
      "section_texts": [
        { "section_id": "sec_4_0", "label": "4.0", "title": "Introduction", "content": "...", "is_prelude": true },
        { "section_id": "sec_4_4_2", "label": "4.2", "title": "...", "content": "..." },
        { "section_id": "sec_4_review", "label": "4.r", "title": "Glossary, Summary & Exercises", "content": "...", "is_review": true }
      ],
      "summary": "...",
      "objectives": ["...", "...", "..."],
      "cards": [{ "topic": "...", "question": "...", "answer": "..." }],
      "deep_theory": {
        "principles": [{"title": "...", "content": "...", "tag": "..."}],
        "formulations": [{"title": "...", "formula": "F = ma", "derivation": "...", "variables": "..."}],
        "mental_models": [{"concept": "...", "analogy": "...", "takeaway": "..."}],
        "misconceptions": [{"trap": "...", "correction": "..."}],
        "key_terms": [{"term": "...", "definition": "..."}],
        "worked_examples": [{"title": "...", "content": "..."}]
      },
      "theory_source": "llm | deterministic"
    }
  ],
  "cards": [ /* flattened for the flashcard runner */ ],
  "quizzes": [],
  "finalExam": []
}
```

**Field notes**

* `theory_source` is per chapter, so a partially enriched course is self-describing.
* `section_texts[].content` is the drill-down payload the UI uses for section-level
  reading; `full_text` keeps the whole cleaned chapter for search/grounding.
* `subsections` is the lightweight tree (no content) for fast list rendering.
* Extra keys are additive — existing consumers (`/api/material/course/{id}`) ignore
  unknown fields, so this schema stays backward compatible.

### 10.2 Payload hygiene

A 34-chapter book with full section text is ~7.8 MB if `full_text` duplicates the
sections. `publish()` therefore runs `slim_course_source_text()`, capping each
chapter's `full_text` at `FULL_TEXT_CAP = 20 000` chars and flagging it with
`full_text_truncated` + `full_text_full_length`. Nothing is lost for the learner:
every section's complete content is preserved in `section_texts`, and the trimmed
tail is the least-read part of the payload.

To re-apply the cap to an already published course (e.g. one built before this
rule existed):

```python
import json
from divide_book import slim_course_source_text
path = "backend/data/courses/custom_phy_college_physics_2e.json"
course = json.load(open(path, encoding="utf-8"))
json.dump(slim_course_source_text(course), open(path, "w", encoding="utf-8"),
          indent=2, ensure_ascii=False)
```

---


## 11. Quality Gates

Run these after every pipeline change.

| # | Check | Expected |
| --- | --- | --- |
| 1 | `python -c "import py_compile; py_compile.compile('divide_book.py', doraise=True)"` | no output |
| 2 | Structure line in stdout | `chapter pattern : 34 chapters via 'chapter_digits'` |
| 3 | TOC parse line | `Front-matter TOC: 34 chapters, 244 sections` |
| 4 | Division line | `Divided into 34 chapters (312 sections)` |
| 5 | Weak-chapter warning | must **not** appear |
| 6 | Chapter titles | from the TOC, no `"… 119 Fundamentals"` junk |
| 7 | Section labels | contiguous `N.0 → N.m → N.r`, no duplicates |
| 8 | `grep "Access for free"` in the course JSON | 0 hits |
| 9 | `theory_source` | `llm` for the enriched range, `deterministic` for the rest |
| 10 | Course is listed | `CourseManager.get_course_by_id(course_id)` returns the course |
| 11 | API smoke | `GET /api/material/course/custom_phy_college_physics_2e` returns `chapters` |
| 12 | Inference unit tests | `python -m pytest tests/test_book_structurer.py -q` → 9 passed |
| 13 | Any-book smoke | `python backend/divide_book.py --file <any book> --inspect` prints a sensible structure + chapter list |

Quick inspection harnesses:

```python
# bundled preset
from divide_book import SmartBookDivider
d = SmartBookDivider("physics"); d.parse_toc(); chs = d.divide()
for c in chs[:3]:
    print(c["chapter_index"], c["title"], c["sections_count"])
    print([s["label"] for s in c["subsections"]])

# any user book (structure inference only, nothing published)
from book_structurer import BookStructurer
plan = BookStructurer(open("book.txt", encoding="utf-8").read()).plan()
print(plan.describe())
```

---

## 12. CLI Reference

```bash
python backend/divide_book.py                                  # deterministic, offline
python backend/divide_book.py --source math                    # other bundled book
python backend/divide_book.py --llm                            # Llama-enriched theory
python backend/divide_book.py --llm --max-chapters 6           # enrich first 6 only
python backend/divide_book.py --subject "Applied Physics" --description "Custom blurb"

# ANY book the user supplies (structure inferred, no preset needed)
python backend/divide_book.py --file "D:/books/biology.pdf"
python backend/divide_book.py --file notes.md --title "My Notes" --subject Biology
python backend/divide_book.py --file notes.md --inspect        # dry run, publishes nothing
python backend/divide_book.py --file notes.md --llm --course-id custom_my_notes
```

| Flag | Default | Meaning |
| --- | --- | --- |
| `--file` | — | Your own book: `.txt`/`.md`, or anything MaterialParser reads (`.pdf`, `.epub`, `.mobi`, `.xps`, `.fb2`) |
| `--title` | filename | Course title for `--file` input |
| `--tier` | `Undergraduate` | Academic tier label for `--file` input |
| `--course-id` | `custom_<slug>` | Explicit course id |
| `--source` | `physics` | Key in `BOOKS` (`physics`, `math`, `calculus`, `biology`); ignored with `--file` |
| `--inspect` | off | Print inferred structure + division summary, publish nothing |
| `--llm` | off | Enrich theory with the local fine-tuned Llama |
| `--max-chapters` | all | Cap LLM enrichment; the rest keeps the deterministic skeleton |
| `--subject` | book subject | Override the subject label written into the course |
| `--description` | generated | Override the course description |

### 12.1 Uploads through the app

The Course Studio upload flow (`POST /api/material/ingest` →
`process_and_ingest_material` in `backend/app.py`) uses the same inference layer:

1. `MaterialParser` extracts + cleans the uploaded bytes (PDF/EPUB/TXT/MD).
2. `_smart_divide_material()` runs `SmartBookDivider(text=..., title=..., subject=...)`.
   If it yields ≥ 2 chapters they are used; otherwise the classic
   `MaterialParser.detect_outline_or_chapters()` path is kept as fallback.
3. Chapters keep their inferred `unit_index`/`unit_name`, `section_texts`,
   `sections_count` and `toc_sections`, so uploaded books get the same Study Map,
   unit badges and section drill-down as the bundled courses.
4. `slim_course_source_text()` caps each `full_text` before persistence.

`SmartBookDivider` is also importable directly for scripts and notebooks:

```python
from divide_book import SmartBookDivider
divider = SmartBookDivider(text=extracted_text, title="My Book", subject="Biology")
divider.run(use_llm=False)          # or .run(use_llm=True, max_chapters=5)
```

---

## 13. Known Limitations & Extension Guide

**Limitations**

1. **Math symbols**: when the source PDF rendered a formula as an image, the text
   keeps only a gap (`"If a vector is multiplied by a scalar quantity , …"`). Only
   formulas that survived as text can be grounded.
2. **Two-column boxes**: OpenStax summary/glossary panels are extracted interleaved.
   They are isolated inside the `N.r` review section, so teaching sections stay clean.
3. **No figure extraction**: captions are kept as text; images are not.
4. **LLM nondeterminism**: a 3B model occasionally breaks the JSON contract —
   mitigated by the simplified retry plus the deterministic fallback.
5. **Section fidelity follows the TOC**: when a TOC omits sections, the pipeline
   falls back to the 500-char body rule and yields fewer, larger sections.
6. **Inference is heuristic**: an exotic layout (headings inside tables, chapter
   titles that look like prose) can still mis-classify. `--inspect` prints the
   chosen pattern, confidence and notes so a bad guess is visible before the
   ~30-minute `--llm` build; `--source` presets remain available as a fallback for
   books you want pinned to a known layout.
7. **Scanned PDFs**: no OCR — `MaterialParser` needs a text layer. A scan yields
   almost no text and the pipeline will report a very short document.
8. **Repeated chapter numbers**: books that restart numbering inside each unit are
   supported (unit assignment is positional), but chapter ids are de-duplicated
   (`ch_4`, `ch_4_2`), so downstream features that assume one `ch_4` per course
   should key on `chapter_id`, not `chapter_index`.

**Adding your own book (no preset needed)**

```bash
python backend/divide_book.py --file "D:/books/anything.pdf" --title "Anything" \
                              --subject Biology --inspect
```

Drop `--inspect` (and optionally add `--llm`) to publish it. Presets are only
needed when you want a pinned unit map or a stable `course_id`:

1. Drop the text file into `backend/data/curriculum/`.
2. Add a `BOOKS` entry: `path`, `title`, `subject`, `tier`, `course_id`.
3. Optionally add an explicit unit map (otherwise declared units or 7-chapter
   buckets are used).
4. Run `python backend/divide_book.py --source <key> --max-chapters 2`, then walk
   the quality gates in §11 before building the full course.

---

## 14. Reference Run (College Physics 2e)

| Metric | Value |
| --- | --- |
| Source | `physics_textbook.txt` — 4,117,220 chars / 82,708 lines |
| Front matter discarded | first 40,688 chars (TOC + preface) |
| Chapters | 34 (all 34 detected, 0 weak) |
| TOC sections | 244 |
| Emitted sections | 312 (incl. per-chapter intro + review) |
| Units | 6 |
| Theory mode | deterministic (offline) or `llm` (`--llm`) |
| Output | `backend/data/courses/custom_phy_college_physics_2e.json` |

