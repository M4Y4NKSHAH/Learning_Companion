"""
================================================================================
 Learning Companion — Smart Book Division & Course Publishing Engine
================================================================================

Splits ANY book the user supplies (or a bundled textbook) the *best way possible*
and publishes it straight into the Course Studio:

    python backend/divide_book.py                                 # bundled physics
    python backend/divide_book.py --source math                   # other bundled books
    python backend/divide_book.py --file "D:/books/my_book.pdf"   # YOUR own book
    python backend/divide_book.py --file notes.md --inspect       # dry run
    python backend/divide_book.py --file notes.md --llm           # Llama theory

What it does:

      -> infers the book's OWN structure (`book_structurer`): heading style,
         front-matter TOC vs running text, section pattern, declared units and
         running headers/footers — never one hardcoded publisher layout,
      -> cuts the book into chapters with exact section boundaries,
      -> groups chapters into study UNITS (declared PART/UNIT headings, a preset
         map, or balanced buckets as the last resort),
      -> attaches source-grounded theory (offline deterministic skeleton),
      -> optionally enriches each chapter with the fine-tuned local Llama
         (JSON mode) via `--llm`,
      -> saves the course JSON into backend/data/courses (auto-listed in the UI).

Why inference instead of regexes: real books say `CHAPTER 4`, `Chapter 4: Cells`,
`# Chapter 4`, `UNIT 3 - Mechanics`, `Lesson 7`, `CHAPTER IV`, `Chapter Four`,
`4. Cells` — or have no headings at all. Every plausible pattern is scored against
the document, and the engine degrades gracefully (size-balanced chunking) so
ingestion never hard-fails.

Accepts `.txt`/`.md` directly and anything MaterialParser can read
(`.pdf`, `.epub`, `.mobi`, `.xps`, `.fb2`). Programmatic use:

    from divide_book import SmartBookDivider
    SmartBookDivider(text=extracted_text, title="My Book",
                     subject="Biology").run(use_llm=False)
================================================================================
"""

import os
import re
import sys
import json
import time
import argparse
from typing import List, Dict, Any, Optional, Tuple

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from book_structurer import (GENERIC_BACKMATTER, BookStructurer,
                             pretty_title_from_filename, slugify)
from course_manager import CourseManager


# --------------------------------------------------------------------------- #
# Pedagogically coherent study-unit mapping for College Physics 2e (34 ch).
# Configurable per book; `None` triggers an automatic balanced-unit fallback.
# --------------------------------------------------------------------------- #
PHYSICS_UNITS: List[Dict[str, Any]] = [
    {"unit": 1, "name": "Foundations & Mechanics", "chapters": list(range(1, 11))},
    {"unit": 2, "name": "Fluids & Thermodynamics", "chapters": list(range(11, 16))},
    {"unit": 3, "name": "Oscillations, Waves & Sound", "chapters": list(range(16, 18))},
    {"unit": 4, "name": "Electricity & Magnetism", "chapters": list(range(18, 25))},
    {"unit": 5, "name": "Optics & Light", "chapters": list(range(25, 28))},
    {"unit": 6, "name": "Modern Physics & Frontiers", "chapters": list(range(28, 35))},
]

BOOKS: Dict[str, Dict[str, Any]] = {
    "physics": {
        "path": os.path.join(backend_dir, "data", "curriculum", "physics_textbook.txt"),
        "title": "College Physics 2e (OpenStax)",
        "subject": "Physics",
        "tier": "Undergraduate",
        "units": PHYSICS_UNITS,
        "course_id": "custom_phy_college_physics_2e",
    },
    "math": {
        "path": os.path.join(backend_dir, "data", "curriculum", "math_textbook.txt"),
        "title": "Algebra & Trigonometry (OpenStax)",
        "subject": "Mathematics",
        "tier": "Class 11-12",
        "units": None,
        "course_id": "custom_math_algebra_trigonometry",
    },
    "calculus": {
        "path": os.path.join(backend_dir, "data", "curriculum", "calculus_textbook.txt"),
        "title": "Calculus (OpenStax)",
        "subject": "Mathematics",
        "tier": "Undergraduate",
        "units": None,
        "course_id": "custom_math_calculus",
    },
    "biology": {
        "path": os.path.join(backend_dir, "data", "curriculum", "biology_textbook.txt"),
        "title": "Biology 2e (OpenStax)",
        "subject": "Biology",
        "tier": "Class 11-12",
        "units": None,
        "course_id": "custom_bio_biology_2e",
    },
}

# --------------------------------------------------------------------------- #
# Payload hygiene: structured section text is the durable asset, so the raw
# chapter blob is capped. Nothing is lost — every section's full content lives
# in `section_texts`, and the tail of `full_text` is the least-read part of the
# payload. Keeps a full 34-chapter book under a few MB on the wire.
# --------------------------------------------------------------------------- #
FULL_TEXT_CAP = 20000


def slim_course_source_text(course: Dict[str, Any], cap: int = FULL_TEXT_CAP) -> Dict[str, Any]:
    """Truncates per-chapter `full_text` while preserving `section_texts`."""
    for ch in course.get("chapters", []) or []:
        text = ch.get("full_text")
        if isinstance(text, str) and len(text) > cap:
            ch["full_text"] = text[:cap]
            ch["full_text_truncated"] = True
            ch["full_text_full_length"] = len(text)
    return course


# --------------------------------------------------------------------------- #
# Chapter-selection specs
#
# A full-book Llama pass costs ~25 s per chapter, so a 41-chapter book takes
# ~17 minutes — far longer than a learner will wait. The builder therefore
# publishes the whole book immediately (structure + deterministic grounded
# theory) and enriches only the chapters the user picked. Selection accepts the
# same syntax a human would write:
#
#     None / "" / "all"   -> every chapter
#     10                  -> the first 10 chapters
#     "10"                -> the first 10 chapters
#     "1-10"              -> chapters 1..10
#     "1,3,5-8"           -> chapters 1, 3, 5, 6, 7, 8
# --------------------------------------------------------------------------- #
def parse_chapter_selection(spec: Any,
                            available: Optional[List[int]] = None) -> Optional[List[int]]:
    """Resolves a selection spec into a sorted list of chapter indices.

    Returns `None` for "everything", an explicit list otherwise. Unknown or
    out-of-range numbers are dropped (never fatal), and an unparseable spec
    falls back to "everything" so a typo can never silently build nothing.
    """
    if spec is None:
        return None
    if isinstance(spec, int) and not isinstance(spec, bool):
        return list(available or [])[:spec] if spec > 0 else None
    if isinstance(spec, (list, tuple, set)):
        wanted = [int(x) for x in spec if str(x).strip().isdigit()]
        return _clamp_selection(wanted, available)

    text = str(spec).strip().lower()
    if not text or text in ("all", "*", "full", "everything", "complete"):
        return None
    if text.isdigit():                       # "10" -> the first ten chapters
        count = int(text)
        if count <= 0:
            return None
        return list(available or [])[:count]

    wanted: List[int] = []
    for part in re.split(r"[,\s]+", text):
        if not part:
            continue
        rng = re.match(r"^(\d+)\s*[-–—:]\s*(\d+)$", part)
        if rng:
            lo, hi = sorted((int(rng.group(1)), int(rng.group(2))))
            wanted.extend(range(lo, hi + 1))
            continue
        if part.isdigit():
            wanted.append(int(part))
            continue
        print(f"[divide_book] Ignoring unrecognised selection token '{part}'.")
    return _clamp_selection(wanted, available)


def _clamp_selection(wanted: List[int], available: Optional[List[int]]) -> Optional[List[int]]:
    """Normalises a numeric selection against the chapters that actually exist."""
    keep = set(available) if available else None
    seen = []
    for num in sorted(set(int(w) for w in wanted)):
        if keep is not None and num not in keep:
            continue
        if num > 0:
            seen.append(num)
    if not seen:
        print("[divide_book] Selection matched no chapters -> synthesizing theory "
              "for the whole book.")
        return None
    return seen


def summarise_selection(targets: List[int], total: int) -> str:
    """`[1,2,3,4,5,9]` -> `chapters 1-5, 9 (6 of 41)` — readable in logs and UI."""
    if not targets:
        return "no chapters (nothing to enrich)"
    runs: List[str] = []
    start = prev = targets[0]
    for num in targets[1:]:
        if num == prev + 1:
            prev = num
            continue
        runs.append(str(start) if start == prev else f"{start}-{prev}")
        start = prev = num
    runs.append(str(start) if start == prev else f"{start}-{prev}")
    shown = ", ".join(runs)
    return f"chapters {shown} ({len(targets)} of {total})"


def estimate_llm_build(planned: int, seconds_per_chapter: float = 25.0) -> Dict[str, int]:
    """Rough pre-run time estimate for the UI (refined with real timings live)."""
    total = max(0, int(planned * seconds_per_chapter))
    return {"seconds": total, "minutes": round(total / 60.0, 1)}


class SmartBookDivider:
    """
    Divides a raw textbook into pedagogically grouped chapters + sections using
    the book's own Table of Contents, then publishes it as a course.

    Why this beats naive regex splitting:
      * The TOC (front matter) is separated from the running text before anything
        else happens, so a chapter is never cut at its own TOC entry.
      * Section headings inside the body are *validated against the TOC*, so
        numbered equations ("1.2") and running page headers
        ("1.1 - Physics: An Introduction 9") can never become fake sections.
      * Page headers / footers / "Access for free at openstax.org" are stripped.
      * Multi-line TOC titles are stitched back together.
    """

    SECTION_RE = re.compile(r"^(\d{1,3})\.(\d{1,3})\s+(.+)$")
    CHAPTER_MARK_RE = re.compile(r"^CHAPTER\s+(\d{1,3})\s*$", re.IGNORECASE)
    CHAPTER_OUTLINE_RE = re.compile(r"^CHAPTER\s+OUTLINE\s*$", re.IGNORECASE)
    # PDF text extraction artefacts:
    #   "1.1 - Physics: An Introduction 9"  -> running page header (bullet separator)
    #   "138  3 - Section Summary"          -> running page footer
    #   "Access for free at openstax.org"   -> licence footer
    BULLET_CHARS = "•·ò"
    PAGE_HEADER_RE = re.compile(r"^\d{1,3}\.\d{1,3}\s*[" + BULLET_CHARS + r"]\s+.+\s\d{1,4}$")
    PAGE_HEADER_RE_2 = re.compile(r"^\d{1,4}\s+\d{1,3}\s*[" + BULLET_CHARS + r"]\s")
    FOOTER_RE = re.compile(r"(Access for free at openstax\.org|"
                           r"This OpenStax book is available for free|Download for free at)", re.I)
    PAGE_MARK_RE = re.compile(r"^---\s*Page \d+\s*---$")
    LEADING_BULLET_RE = re.compile(r"^[" + BULLET_CHARS + r"]\s*")
    BACKMATTER_RE = re.compile(
        r"^(Glossary|Section Summary|Summary|Conceptual Questions|Problems\s*&\s*Exercises|"
        r"Problems and Exercises|Exercises|Key Terms|Chapter Review)\s*$", re.IGNORECASE)

    def __init__(self, book_key: Optional[str] = None, *,
                 path: Optional[str] = None, text: Optional[str] = None,
                 title: Optional[str] = None, subject: Optional[str] = None,
                 tier: Optional[str] = None, course_id: Optional[str] = None,
                 units: Optional[List[Dict[str, Any]]] = None,
                 extracted_book: Optional[Any] = None):
        """Accepts either a bundled preset key or any user-supplied book.

        `path` may be .txt/.md or any format MaterialParser can read
        (.pdf/.epub/.mobi/.xps/.fb2); `text` allows raw in-memory content
        (pasted notes, API payloads). Structure is always inferred, never assumed.
        """
        if path or text or extracted_book is not None:
            self.book = self._ad_hoc_book(path=path, text=text, title=title,
                                          subject=subject, tier=tier,
                                          course_id=course_id, units=units)
        else:
            book_key = book_key or "physics"
            if book_key not in BOOKS:
                raise ValueError(f"Unknown book '{book_key}'. Choose from: {list(BOOKS.keys())}")
            self.book = dict(BOOKS[book_key])

        path = self.book.get("path")
        self.extracted_book = extracted_book
        if self.extracted_book is not None:
            self.raw_text = text if text is not None else getattr(self.extracted_book, "text", "")
            self.structurer = BookStructurer(self.raw_text, extracted_book=self.extracted_book, outline=getattr(self.extracted_book, "outline", None))
        elif path and os.path.exists(path) and os.path.splitext(path)[1].lower() == ".pdf":
            try:
                from backend.book_extract import extract_pdf
            except ImportError:
                from book_extract import extract_pdf
            try:
                self.extracted_book = extract_pdf(path)
                self.raw_text = self.extracted_book.text
                self.structurer = BookStructurer(self.raw_text, extracted_book=self.extracted_book, outline=self.extracted_book.outline)
            except Exception as e:
                print(f"[divide_book] PDF extraction failed: {e}. Falling back to standard loader.")
                self.raw_text = self._load_source(self.book)
                self.structurer = BookStructurer(self.raw_text)
        else:
            self.raw_text = self._load_source(self.book)
            self.structurer = BookStructurer(self.raw_text)

        self.plan = self.structurer.plan()
        print("[divide_book] Inferred structure:")
        for line in self.plan.describe().split("\n"):
            print(f"  {line}")

        self.body_start: int = self.plan.body_start
        self.chapters: List[Dict[str, Any]] = []
        self.toc: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------ #
    # Source loading (bundled preset OR arbitrary user book)
    # ------------------------------------------------------------------ #
    @staticmethod
    def _load_source(book: Dict[str, Any]) -> str:
        if book.get("text") is not None:
            return book["text"]
        path = book.get("path")
        if not path:
            return ""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Source book not found: {path}")
        ext = os.path.splitext(path)[1].lower()
        if ext in (".pdf", ".epub", ".mobi", ".xps", ".fb2"):
            from material_parser import MaterialParser
            return MaterialParser.extract_text_from_file(path)
        for encoding in ("utf-8", "utf-8-sig", "latin-1"):
            try:
                with open(path, "r", encoding=encoding) as fh:
                    return fh.read()
            except UnicodeDecodeError:
                continue
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()

    @staticmethod
    def _ad_hoc_book(**kw: Any) -> Dict[str, Any]:
        path = kw.get("path")
        title = kw.get("title") or (pretty_title_from_filename(path) if path else "Untitled Book")
        return {
            "path": path,
            "text": kw.get("text"),
            "title": title,
            "subject": kw.get("subject") or "General",
            "tier": kw.get("tier") or "Undergraduate",
            "units": kw.get("units"),
            "course_id": kw.get("course_id") or f"custom_{slugify(title)}",
        }

    # ------------------------------------------------------------------ #
    # 0. Front matter (TOC) vs. running text separation
    # ------------------------------------------------------------------ #
    def _chapter_markers(self) -> List[Tuple[int, int]]:
        """Heading positions chosen by the structure-inference pass.

        Deliberately not hardcoded to `CHAPTER N`: the structurer scores every
        plausible heading style for this document (see book_structurer).
        """
        plan = getattr(self, "plan", None)
        if plan and plan.chapter_matches:
            return [(spot.pos, spot.number) for spot in plan.chapter_matches]
        return []

    def _find_body_start(self) -> int:
        """Where the running text starts (front-matter TOC excluded)."""
        return getattr(self.plan, "body_start", 0) or 0

    # ------------------------------------------------------------------ #
    # 1. Table of Contents parsing
    # ------------------------------------------------------------------ #
    def parse_toc(self) -> List[Dict[str, Any]]:
        """
        Extracts chapter -> sections from the front-matter TOC only. Handles the
        OpenStax layout:

            CHAPTER 1
            Introduction: The Nature of Science and Physics 7
            1.1 Physics: An Introduction 8
            ...
            1.4 Approximation 31
            Glossary 34
        """
        self.body_start = self._find_body_start()
        if getattr(self, "plan", None) and self.plan.parsed_chapters and len(self.plan.parsed_chapters) >= 3:
            self.toc = self.plan.parsed_chapters
            print(f"[divide_book] {self.plan.source.title()} structure: {len(self.toc)} chapters, "
                  f"{sum(len(c.get('sections', [])) for c in self.toc)} sections.")
            return self.toc

        front = self.raw_text[:self.body_start]
        lowered = front.lower()
        c_idx = lowered.find("contents")
        if c_idx != -1:
            front = front[c_idx:]

        toc: List[Dict[str, Any]] = []
        current: Optional[Dict[str, Any]] = None
        title_parts: List[str] = []
        awaiting_title = False

        def _finalize_title():
            nonlocal awaiting_title
            if current is not None and title_parts:
                current["title"] = re.sub(r"\s{2,}", " ", " ".join(title_parts)).strip()
            title_parts.clear()
            awaiting_title = False

        for raw_line in front.split("\n"):
            line = raw_line.strip().replace("\u00f2", " ").strip()
            if not line:
                continue
            cm = self.CHAPTER_MARK_RE.match(line)
            if cm:
                current = {"chapter": int(cm.group(1)), "title": "", "sections": [],
                           "page": None}
                toc.append(current)
                title_parts.clear()
                awaiting_title = True
                continue
            if current is None:
                continue
            sm = self.SECTION_RE.match(line)
            if sm and int(sm.group(1)) == current["chapter"]:
                _finalize_title()
                title = self._strip_page_number(sm.group(3))
                current["sections"].append({"label": f"{sm.group(1)}.{sm.group(2)}",
                                            "title": title})
                continue
            if awaiting_title and re.search(r"[A-Za-z]{3,}", line):
                pg = re.search(r"\s+(\d{1,4})\s*$", line)
                title_parts.append(self._strip_page_number(line))
                if pg:
                    current["page"] = int(pg.group(1))
                    _finalize_title()
                continue

        _finalize_title()

        self.toc = [c for c in toc if c.get("title") and c.get("sections")]
        print(f"[divide_book] Front-matter TOC: {len(self.toc)} chapters, "
              f"{sum(len(c['sections']) for c in self.toc)} sections.")
        if len(self.toc) < 3:
            self.toc = self._synthesize_toc_from_plan()
        return self.toc

    def _synthesize_toc_from_plan(self) -> List[Dict[str, Any]]:
        """Builds a table of contents from the inferred headings.

        Most user books (notes, papers, EPUB dumps) have no parseable
        front-matter TOC, so the headings the structurer found *are* the TOC.
        """
        out: List[Dict[str, Any]] = []
        for spot in self.plan.chapter_matches:
            out.append({
                "chapter": spot.number,
                "title": spot.title or spot.line,
                "sections": [],
                "page": None,
                "pos": spot.pos,
            })
        if out:
            print(f"[divide_book] No usable front-matter TOC -> synthesized "
                  f"{len(out)} chapter entries from inferred headings.")
        return out

    @staticmethod
    def _strip_page_number(text: str) -> str:
        return re.sub(r"\s+\d{1,4}\s*$", "", text).strip()

    # ------------------------------------------------------------------ #
    # 2. Chapter body extraction (TOC-verified boundaries)
    # ------------------------------------------------------------------ #
    def _locate_chapter_bodies(self) -> List[Dict[str, Any]]:
        """
        Returns one boundary record per *unique* chapter number found in the
        running text (everything after the front-matter TOC). Starts are the
        'CHAPTER N' headings; ends are the next chapter's heading.
        """
        text = self.raw_text
        markers = [(pos, num) for pos, num in self._chapter_markers()
                   if pos >= self.body_start]
        boundaries: List[Dict[str, Any]] = []
        # No dedupe by number: books that restart numbering inside each unit
        # legitimately reuse chapter numbers, and the structurer has already
        # pruned the front-matter TOC copies of the headings.
        for idx, (pos, num) in enumerate(markers):
            end = markers[idx + 1][0] if idx + 1 < len(markers) else len(text)
            boundaries.append({"chapter": num, "start": pos, "end": end})

        if not boundaries:
            boundaries = self._section_anchor_fallback()
        boundaries.sort(key=lambda b: b["start"])
        # Recompute ends after sorting so a stray out-of-order marker cannot cut a chapter
        for i, b in enumerate(boundaries):
            if i + 1 < len(boundaries):
                b["end"] = boundaries[i + 1]["start"]
        print(f"[divide_book] Located {len(boundaries)} chapter bodies in the running text.")
        return boundaries

    def _section_anchor_fallback(self) -> List[Dict[str, Any]]:
        """Fallback for books that omit 'CHAPTER N' in the body: anchor on the
        first section heading of each TOC chapter, taken from the body region."""
        text = self.raw_text
        found: List[Dict[str, Any]] = []
        for chapter in self.toc:
            if not chapter["sections"]:
                continue
            label = chapter["sections"][0]["label"]
            hits = [m.start() for m in re.finditer(
                r"(?m)^\s*" + re.escape(label) + r"\s+[A-Z]", text)]
            hits = [h for h in hits if h >= self.body_start]
            if hits:
                found.append({"chapter": chapter["chapter"], "start": hits[0], "end": None})
        found.sort(key=lambda b: b["start"])
        for i, b in enumerate(found):
            b["end"] = found[i + 1]["start"] if i + 1 < len(found) else len(text)
        return found

    def _is_noise(self, line: str) -> bool:
        s = line.strip()
        if not s:
            return True
        if self.FOOTER_RE.search(s) or self.PAGE_MARK_RE.match(s):
            return True
        if self.PAGE_HEADER_RE.match(s) or self.PAGE_HEADER_RE_2.match(s):
            return True
        # Publisher-agnostic suppression: any line shape that repeats with a page
        # number (discovered by the structurer) is a running header/footer.
        if self.plan.is_running_line(s):
            return True
        return False

    @staticmethod
    def _normalize_line(line: str) -> str:
        """Turns the PDF's bullet glyph into a markdown-ish dash and squeezes
        stray spaces left by symbol-in-image extraction."""
        s = SmartBookDivider.LEADING_BULLET_RE.sub("- ", line.rstrip())
        return re.sub(r"[ \t]{2,}", " ", s)

    def _clean_body_text(self, body: str) -> str:
        cleaned = [self._normalize_line(ln) for ln in body.split("\n")
                   if not self._is_noise(ln)]
        text = "\n".join(cleaned)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _find_section_start_indexes(self, lines: List[str], chapter_num: int,
                                   toc_sections: List[Dict[str, str]]) -> List[int]:
        """
        Picks the *real* heading line index for every TOC section of this chapter.

        The real heading is the first heading-shaped line that appears after the
        in-chapter "CHAPTER OUTLINE" list. Subsequent repeats are page headers,
        which are rejected by `_is_noise`.
        """
        valid_labels = {s["label"] for s in toc_sections}
        search_from = 0
        for i, ln in enumerate(lines):
            if self.CHAPTER_OUTLINE_RE.match(ln.strip()):
                j = i + 1
                while j < len(lines):
                    s = lines[j].strip()
                    if not s:
                        j += 1
                        continue
                    if self.SECTION_RE.match(s):
                        j += 1
                        continue
                    break
                search_from = j
                break

        starts: Dict[str, int] = {}
        for i in range(search_from, len(lines)):
            s = lines[i].strip()
            if self._is_noise(s):
                continue
            # Running headers masquerade as headings ("1.1 - Title 9")
            if re.search(r"[" + self.BULLET_CHARS + r"]", s):
                continue
            m = self.SECTION_RE.match(s)
            if not m or int(m.group(1)) != chapter_num:
                continue
            label = f"{m.group(1)}.{m.group(2)}"
            if label not in valid_labels or label in starts:
                continue
            title = self._strip_page_number(m.group(3))
            if len(title) < 3 or not re.search(r"[A-Za-z]{3,}", title):
                continue
            # A real heading is short; a line with a full sentence is body prose
            # that merely starts with a number (e.g. a numbered equation).
            if len(s) > 110:
                continue
            starts[label] = i

        ordered = sorted(starts.items(), key=lambda kv: kv[1])
        return [idx for _label, idx in ordered]

    def _split_sections(self, body: str, chapter_num: int,
                        toc_sections: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """Splits a chapter body into its TOC-declared sections plus an intro
        section and a chapter-review (glossary/exercises) section."""
        if not toc_sections:
            return self._split_sections_generic(body, chapter_num)
        lines = body.split("\n")
        start_indexes = self._find_section_start_indexes(lines, chapter_num, toc_sections)

        # Where does the chapter's back matter begin (Glossary / Summary /
        # Conceptual Questions / Problems & Exercises)?
        review_start = None
        for i, ln in enumerate(lines):
            if self.BACKMATTER_RE.match(ln.strip()):
                review_start = i
                break

        sections: List[Dict[str, Any]] = []

        # ---- Chapter intro (everything before the first real section) -------
        intro_end = start_indexes[0] if start_indexes else len(lines)
        if review_start is not None:
            intro_end = min(intro_end, review_start)
        intro_lines = [ln for ln in lines[:intro_end]
                       if not self.CHAPTER_OUTLINE_RE.match(ln.strip())
                       and not self.CHAPTER_MARK_RE.match(ln.strip())
                       and not self.SECTION_RE.match(ln.strip())]
        intro_text = self._clean_body_text("\n".join(intro_lines))
        if len(intro_text) > 120:
            sections.append({
                "section_id": f"sec_{chapter_num}_0",
                "label": f"{chapter_num}.0",
                "title": "Introduction",
                "content": intro_text,
                "is_prelude": True,
            })

        # ---- TOC-declared sections -----------------------------------------
        for i, start in enumerate(start_indexes):
            end = start_indexes[i + 1] if i + 1 < len(start_indexes) else len(lines)
            if review_start is not None:
                end = min(end, review_start)
            m = self.SECTION_RE.match(lines[start].strip())
            label = f"{m.group(1)}.{m.group(2)}" if m else f"{chapter_num}.{i + 1}"
            meta = next((s for s in toc_sections if s["label"] == label), None)
            # PDF extraction often glues the first sentence onto the heading line:
            # "3.3 Vector Addition ... Analytical Methods The analytical method ..."
            reminder = ""
            heading_line = lines[start].strip()
            if meta:
                prefix = re.compile(r"^\s*" + re.escape(label) + r"\s+" +
                                    re.escape(meta["title"]))
                pm = prefix.match(heading_line)
                if pm:
                    reminder = heading_line[pm.end():].strip()
            body_part = "\n".join(lines[start + 1:end])
            content = self._clean_body_text((reminder + "\n" + body_part).strip()
                                            if reminder else body_part)
            if len(content) < 80:
                continue
            sections.append({
                "section_id": f"sec_{chapter_num}_{label.replace('.', '_')}",
                "label": label,
                "title": meta["title"] if meta else self._strip_page_number(lines[start].strip()),
                "content": content,
            })

        # ---- Chapter review (glossary / summary / exercises) ---------------
        if review_start is not None:
            review_text = self._clean_body_text("\n".join(lines[review_start:]))
            if len(review_text) > 200:
                sections.append({
                    "section_id": f"sec_{chapter_num}_review",
                    "label": f"{chapter_num}.r",
                    "title": "Glossary, Summary & Exercises",
                    "content": review_text,
                    "is_review": True,
                })
        return sections

    def _generic_review_start(self, lines: List[str]) -> Optional[int]:
        """First back-matter heading (Summary / Exercises / Glossary / ...)."""
        for i, raw in enumerate(lines):
            s = raw.strip()
            if not s:
                continue
            if self.BACKMATTER_RE.match(s):
                return i
            if s.lower().rstrip(":.") in GENERIC_BACKMATTER:
                return i
        return None

    def _split_sections_generic(self, body: str, chapter_num: int) -> List[Dict[str, Any]]:
        """Section map for books without a numbered TOC.

        Uses the heading family the structurer chose for this book ("3.4",
        "3 - Title", "# Heading", "A. Title"), and if the book has no usable
        headings at all it falls back to size-balanced chunk sections so the
        Study Map is never empty.
        """
        lines = body.split("\n")
        starts = self.structurer.section_starts(body, chapter_num, self.plan)
        review_start = self._generic_review_start(lines)
        limit = review_start if review_start is not None else len(lines)

        def content(a: int, b: int) -> str:
            return self._clean_body_text("\n".join(lines[a:b]))

        sections: List[Dict[str, Any]] = []
        usable = [s for s in starts if s[0] < limit]
        first = usable[0][0] if usable else limit

        intro = content(0, first)
        if len(intro) > 120:
            sections.append({
                "section_id": f"sec_{chapter_num}_0",
                "label": f"{chapter_num}.0",
                "title": "Introduction",
                "content": intro,
                "is_prelude": True,
            })

        for k, (idx, label, title) in enumerate(usable):
            end = usable[k + 1][0] if k + 1 < len(usable) else limit
            text = content(idx + 1, end)
            if len(text) < 80:
                continue
            sections.append({
                "section_id": f"sec_{chapter_num}_{label.replace('.', '_')}",
                "label": label,
                "title": title,
                "content": text,
            })

        if not any(not s.get("is_prelude") and not s.get("is_review") for s in sections):
            sections.extend(self._chunk_sections(body, chapter_num))

        if review_start is not None:
            review = content(review_start, len(lines))
            if len(review) > 200:
                sections.append({
                    "section_id": f"sec_{chapter_num}_review",
                    "label": f"{chapter_num}.r",
                    "title": "Glossary, Summary & Exercises",
                    "content": review,
                    "is_review": True,
                })
        return sections

    def _chunk_sections(self, body: str, chapter_num: int,
                        target_chars: int = 3200, max_chunks: int = 8) -> List[Dict[str, Any]]:
        """Heading-less fallback: size-balanced study blocks."""
        out: List[Dict[str, Any]] = []
        for k, chunk in enumerate(self.structurer.chunk_text(
                body, target_chars=target_chars, max_chunks=max_chunks), 1):
            if len(chunk.strip()) < 80:
                continue
            out.append({
                "section_id": f"sec_{chapter_num}_c{k}",
                "label": f"{chapter_num}.{k}",
                "title": self.structurer.fallback_title(chunk) or f"Study Block {k}",
                "content": self._clean_body_text(chunk),
                "is_chunk": True,
            })
        return out

    # ------------------------------------------------------------------ #
    # 3. Unit grouping & full division
    # ------------------------------------------------------------------ #
    @staticmethod
    def _clean_chapter_title(num: int, title: str) -> str:
        """Strips a publisher prefix (`CHAPTER 4`, `Chapter Four:`) from titles."""
        t = re.sub(r"(?i)^\s*(?:chapter|unit|part|lesson|module|lecture|week|topic)\s+"
                   r"(?:\d{1,3}|[IVXLCDM]{1,7}|[A-Za-z]+)\s*[:.\-–—)]?\s*", "", title or "").strip()
        t = re.sub(r"^\s*\d{1,3}\s*[:.\-–—)]?\s+", "", t).strip()
        return t or (title or "").strip()

    def _unit_for_chapter(self, chapter_num: int,
                          pos: Optional[int] = None) -> Dict[str, Any]:
        """Preset unit map > units declared in the book > balanced buckets.

        Books that restart chapter numbering inside each unit are handled by
        position, so lesson 1 of unit 2 is not merged into unit 1.
        """
        units = self.book.get("units") or self.plan.units
        if units:
            if pos is not None:
                for u in units:
                    if u.get("start") is not None and u["start"] <= pos < u.get("end", 1 << 62):
                        return {"unit_index": u["unit"], "unit_name": u["name"]}
            for u in units:
                if chapter_num in u.get("chapters", []):
                    return {"unit_index": u["unit"], "unit_name": u["name"]}
        idx = (chapter_num - 1) // 7
        return {"unit_index": idx + 1, "unit_name": f"Unit {idx + 1}"}

    def divide(self) -> List[Dict[str, Any]]:
        """Executes the full division and returns chapter dictionaries."""
        if not self.toc:
            self.parse_toc()
        boundaries = self._locate_chapter_bodies()
        by_num = {c["chapter"]: c for c in self.toc}
        # Position match wins: books that restart numbering per unit reuse numbers.
        by_pos = {c["pos"]: c for c in self.toc if "pos" in c}

        chapters: List[Dict[str, Any]] = []
        id_uses: Dict[str, int] = {}
        for b in boundaries:
            num = b["chapter"]
            meta = by_pos.get(b["start"]) or by_num.get(num)
            if not meta or not meta.get("title"):
                continue
            body = self._clean_body_text(self.raw_text[b["start"]:b["end"]])
            if len(body) < 500:
                continue
            sections = self._split_sections(body, num, meta["sections"])
            unit = self._unit_for_chapter(num, pos=b["start"])
            base_id = f"ch_{num}"
            id_uses[base_id] = id_uses.get(base_id, 0) + 1
            chapter_id = base_id if id_uses[base_id] == 1 else f"{base_id}_{id_uses[base_id]}"
            seen_sub_keys = set()
            deduped_subsections = []
            for s in sections:
                key = (s.get("label") or s.get("section_id") or s.get("title") or "").strip().lower()
                if key and key in seen_sub_keys:
                    continue
                if key:
                    seen_sub_keys.add(key)
                deduped_subsections.append({
                    "section_id": s["section_id"],
                    "label": s["label"],
                    "title": s["title"]
                })

            clean_ch_title = self._clean_chapter_title(num, meta['title'])
            chapters.append({
                "chapter_id": chapter_id,
                "chapter_index": num,
                "title": f"Chapter {num}: {clean_ch_title}",
                "unit_index": unit["unit_index"],
                "unit_name": unit["unit_name"],
                "toc_sections": [s["label"] for s in meta["sections"]],
                "sections_count": len(sections),
                "subsections": deduped_subsections,
                "content_preview": body[:420],
                "full_text": body,
                "section_texts": sections,
            })

        chapters.sort(key=lambda c: c["chapter_index"])
        self.chapters = chapters
        print(f"[divide_book] Divided into {len(chapters)} chapters "
              f"({sum(c['sections_count'] for c in chapters)} sections) from "
              f"'{self.book['title']}'.")
        missing = [c['chapter_index'] for c in chapters if c['sections_count'] <= 1]
        if missing:
            print(f"[divide_book] ⚠ chapters with weak section detection: {missing}")
        return chapters

    # ------------------------------------------------------------------ #
    # 4. Theory synthesis (deterministic skeleton or local-Llama enrichment)
    # ------------------------------------------------------------------ #
    def synthesize_chapter(self, chapter: Dict[str, Any], use_llm: bool,
                           subject: str, tier: str,
                           include_cards: bool = True) -> Dict[str, Any]:
        """
        Builds the study payload for ONE chapter and returns it.

        The engine always builds a deterministic, source-grounded skeleton first
        and lets the local fine-tuned Llama enrich it in JSON mode; any field the
        model hallucinates is rejected by the grounding pass inside the engine.

        `include_cards=False` skips the second model call, which roughly halves
        the wall-clock time per chapter when the learner only needs theory.
        """
        from question_generator import QuestionGeneratorEngine

        engine = getattr(self, "_engine", None)
        if engine is None:
            engine = QuestionGeneratorEngine()
            self._engine = engine

        text = chapter.get("full_text", "")
        theory = engine.generate_chapter_theory_and_cards(
            chapter_title=chapter.get("title", ""),
            # The local 3B model has a small working context: feed it the
            # chapter's opening sections, which carry the definitions/formulas.
            chapter_text=text[:9000] if use_llm else text[:6000],
            subject=subject,
            tier=tier,
            chapter_index=chapter.get("chapter_index", 1),
            use_llm=use_llm,
            # Local-first contract: never fall out to a cloud model mid-build.
            allow_cloud_fallback=False,
            include_cards=include_cards,
        )
        chapter["summary"] = theory.get("summary", "")
        chapter["objectives"] = theory.get("objectives", [])
        chapter["cards"] = theory.get("cards", [])
        chapter["deep_theory"] = theory.get("deep_theory", {})
        # Trust the engine's own report of how the theory was produced; fall back
        # to the request intent only if the engine did not say.
        chapter["theory_source"] = theory.get("theory_source",
                                             "llm" if use_llm else "deterministic")
        return chapter

    def plan_chapters(self, chapters: List[Dict[str, Any]],
                      enrich_spec: Any = None,
                      resume: bool = False) -> List[int]:
        """Resolves which chapter indices a build should hand to the Llama.

        Honours the selection spec and, when `resume` is set, skips chapters that
        already carry Llama theory so "continue later" never repeats expensive
        work.
        """
        available = [ch.get("chapter_index", i) for i, ch in enumerate(chapters, 1)]
        selected = parse_chapter_selection(enrich_spec, available)
        targets = selected if selected is not None else list(available)

        if resume:
            done = {ch.get("chapter_index") for ch in chapters
                    if ch.get("theory_source") == "llm"}
            skipped = [n for n in targets if n in done]
            targets = [n for n in targets if n not in done]
            if skipped:
                print(f"[divide_book] Resume: {len(skipped)} chapter(s) already "
                      f"enriched, skipping {skipped}.")
        return targets

    def synthesize_theory(self, chapters: List[Dict[str, Any]], use_llm: bool,
                          max_chapters: Optional[int] = None,
                          subject_override: Optional[str] = None,
                          enrich_chapters: Any = None,
                          resume: bool = False,
                          include_cards: bool = True,
                          on_progress: Optional[Any] = None,
                          publish_cb: Optional[Any] = None,
                          publish_every: int = 1) -> List[Dict[str, Any]]:
        """
        Attaches theory to every chapter — fast, and never half-empty.

        `use_llm=False`  -> fully deterministic, offline, instant (all chapters).
        `use_llm=True`   -> only the chapters named by `enrich_chapters` (or the
                            first `max_chapters`) are enriched by the local Llama;
                            every other chapter still receives the deterministic
                            grounded skeleton, so the course is complete and
                            readable the moment the structure is published.

        Accuracy features:
          * `enrich_chapters` — an exact subset (`10`, `"1-10"`, `"1,3,5-8"`).
          * `resume`          — never re-enrich a chapter already marked `llm`.
          * `publish_cb`      — called every `publish_every` chapters so a build
                                interrupted at chapter 7 still keeps 1-7.
          * `on_progress`     — receives measured ETA/coverage for the UI.
        """
        subject = subject_override or self.book["subject"]
        tier = self.book["tier"]
        total = len(chapters)

        spec = enrich_chapters if enrich_chapters is not None else max_chapters
        targets = self.plan_chapters(chapters, spec, resume) if use_llm else []
        target_set = set(targets)
        planned = len(targets)

        avg_seconds = None
        started_all = time.time()
        llm_done = 0

        if use_llm:
            if planned == 0:
                print("[divide_book] Nothing left to enrich — every selected chapter "
                      "already has Llama theory.")
            else:
                print(f"[divide_book] Enriching {planned}/{total} chapter(s) with the "
                      f"local Llama; the other {max(0, total - planned)} keep the "
                      f"grounded deterministic skeleton (course stays complete).")
                print(f"[divide_book] Selection: {summarise_selection(targets, total)}")
        else:
            print(f"[divide_book] Deterministic skeleton for all {total} chapters.")

        for idx, ch in enumerate(chapters, 1):
            num = ch.get("chapter_index", idx)
            use = num in target_set
            print(f"  [{idx}/{total}] ch {num}: {ch.get('title', '')[:52]}  "
                  f"({'llama' if use else 'deterministic'})", flush=True)

            started = time.time()
            self.synthesize_chapter(ch, use_llm=use, subject=subject, tier=tier,
                                    include_cards=include_cards)
            if not use:
                continue

            llm_done += 1
            elapsed = time.time() - started
            # Measured, not guessed: average of the chapters actually run.
            avg_seconds = (elapsed if avg_seconds is None
                           else (avg_seconds * (llm_done - 1) + elapsed) / llm_done)
            if on_progress:
                on_progress(self._progress_payload(
                    llm_done, planned, total, num, ch, avg_seconds,
                    elapsed_total=time.time() - started_all))
            if publish_cb and publish_every and llm_done % publish_every == 0:
                publish_cb(chapters)

        # Flush any chapters enriched since the last periodic publish.
        if publish_cb and planned and (llm_done == 0 or llm_done % max(1, publish_every)):
            publish_cb(chapters)
        if on_progress:
            on_progress(self._progress_payload(
                llm_done, planned, total, None, None, avg_seconds,
                elapsed_total=time.time() - started_all, final=True))
        return chapters

    def _progress_payload(self, done: int, planned: int, total: int,
                          chapter_num: Optional[int], chapter: Optional[Dict[str, Any]],
                          avg_seconds: Optional[float],
                          elapsed_total: float = 0.0,
                          final: bool = False) -> Dict[str, Any]:
        """Measured build progress (counts, notes, and a real ETA)."""
        remaining = max(0, planned - done)
        eta = int(remaining * avg_seconds) if avg_seconds else None
        return {
            "chapters_enriched": done,
            "chapters_planned": planned,
            "chapters_total": total,
            "chapter_index": chapter_num,
            "chapter_title": (chapter or {}).get("title", "") if chapter else "",
            "avg_seconds_per_chapter": round(avg_seconds, 1) if avg_seconds else None,
            "eta_seconds": eta,
            "elapsed_seconds": int(elapsed_total),
            "done": final,
        }

    def theory_coverage(self, chapters: List[Dict[str, Any]]) -> Dict[str, Any]:
        """What the learner should expect: which chapters are Llama-enriched."""
        enriched = [ch.get("chapter_index") for ch in chapters
                    if ch.get("theory_source") == "llm"]
        total = len(chapters)
        return {
            "enriched_chapters": enriched,
            "enriched_count": len(enriched),
            "chapters_total": total,
            "pending_count": max(0, total - len(enriched)),
            "complete": total > 0 and len(enriched) >= total,
        }

    # ------------------------------------------------------------------ #
    # 5. Publishing (saves the course into backend/data/courses)
    # ------------------------------------------------------------------ #
    def publish(self, chapters: List[Dict[str, Any]],
                description: Optional[str] = None) -> str:
        """Writes the divided book as a course JSON so it shows up in the
        Course Studio library immediately."""
        units = {}
        for ch in chapters:
            units.setdefault(ch.get("unit_index", 1), ch.get("unit_name", ""))
        total_cards = sum(len(ch.get("cards", [])) for ch in chapters)
        coverage = self.theory_coverage(chapters)
        course = {
            "course_id": self.book["course_id"],
            "title": self.book["title"],
            "subject": self.book["subject"],
            "academic_tier": self.book["tier"],
            "is_builtin": False,
            "source_book": os.path.basename(self.book.get("path") or self.book["title"]),
            # `theory_coverage` tells the learner exactly what is Llama-enriched
            # and what is still on the (complete) deterministic skeleton, so a
            # partial build never looks like missing content.
            "theory_coverage": coverage,
            "description": description or (
                f"Complete division of '{self.book['title']}' into {len(chapters)} "
                f"chapters grouped into {len(units)} study units. Titles and sections "
                f"come from the book's own table of contents; theory is grounded in "
                f"the source text. Llama-enriched chapters: "
                f"{coverage['enriched_count']}/{coverage['chapters_total']}."
            ),
            "chapters_count": len(chapters),
            "sections_count": sum(ch.get("sections_count", 0) for ch in chapters),
            "unit_count": len(units),
            "units": [{"unit_index": k, "unit_name": v} for k, v in sorted(units.items())],
            "flashcards_count": total_cards,
            "quizzes_count": 0,
            "exam_questions_count": 0,
            "chapters": chapters,
            "cards": [c for ch in chapters for c in ch.get("cards", [])],
            "quizzes": [],
            "finalExam": [],
        }
        course_id = CourseManager.save_custom_course(slim_course_source_text(course))
        print(f"[divide_book] Published '{course['title']}'")
        print(f"[divide_book]   course_id : {course_id}")
        print(f"[divide_book]   chapters  : {len(chapters)} | sections: "
              f"{course['sections_count']} | units: {course['unit_count']} | "
              f"cards: {total_cards}")
        if not coverage["complete"]:
            print(f"[divide_book]   enrichment: {coverage['enriched_count']}/"
                  f"{coverage['chapters_total']} chapters Llama-enriched "
                  f"(remaining chapters use the grounded deterministic skeleton; "
                  f"run again with --resume to enrich more).")
        return course_id

    def run(self, use_llm: bool = False, max_chapters: Optional[int] = None,
            subject_override: Optional[str] = None,
            description: Optional[str] = None,
            enrich_chapters: Any = None,
            resume: bool = False,
            include_cards: bool = True,
            publish_every: int = 1,
            on_progress: Optional[Any] = None,
            skeleton_first: bool = True) -> Dict[str, Any]:
        """
        Full pipeline: parse TOC -> divide -> synthesize theory -> publish.

        Two-phase build (`--llm`):
          Phase 1  structure + deterministic grounded theory for every chapter is
                   published immediately, so the course is openable in seconds.
          Phase 2  the selected chapters are enriched by the local Llama and the
                   course is re-published as each one lands, so an interrupted
                   build keeps everything it already produced.
        """
        print(f"[divide_book] Source: {self.book['title']}")
        self.parse_toc()
        chapters = self.divide()
        if not chapters:
            raise RuntimeError("Division produced zero chapters — check the source format.")

        spec = enrich_chapters if enrich_chapters is not None else max_chapters

        # ---- Phase 1: complete, instantly-usable course -------------------- #
        first_publish = None
        if use_llm and skeleton_first:
            print(f"[divide_book] Phase 1/2: publishing the full structure + grounded "
                  f"deterministic theory for all {len(chapters)} chapters "
                  f"(available immediately)...")
            self.synthesize_theory(chapters, use_llm=False,
                                   subject_override=subject_override)
            first_publish = self.publish(chapters, description=description)

        # ---- Phase 2: selective Llama enrichment --------------------------- #
        targets = self.plan_chapters(chapters, spec, resume) if use_llm else []
        planned = len(targets)
        if use_llm and planned:
            est = estimate_llm_build(planned)
            print(f"[divide_book] Phase 2/2: enriching "
                  f"{summarise_selection(targets, len(chapters))} "
                  f"(~{est['minutes']} min at ~25 s/chapter)...")

        def _publish(_chs=None):
            self.publish(chapters, description=description)

        chapters = self.synthesize_theory(
            chapters, use_llm=use_llm,
            max_chapters=max_chapters,
            subject_override=subject_override,
            enrich_chapters=enrich_chapters,
            resume=resume,
            include_cards=include_cards,
            on_progress=on_progress,
            publish_cb=_publish if use_llm else None,
            publish_every=publish_every,
        )
        self.publish(chapters, description=description)

        coverage = self.theory_coverage(chapters)
        return {"course_id": self.book["course_id"], "chapters": len(chapters),
                "mode": "llm" if use_llm else "deterministic",
                "first_publish": first_publish,
                "theory_coverage": coverage,
                "enriched_count": coverage["enriched_count"]}


def main():
    parser = argparse.ArgumentParser(
        description="Divide ANY book (user-supplied file, pasted text, or a bundled "
                    "textbook) into units + chapters and publish it into the Course "
                    "Studio. Structure is inferred from the book itself.")
    parser.add_argument("--file", default=None,
                        help="Path to your own book: .txt/.md or anything "
                             "MaterialParser reads (.pdf/.epub/.mobi/.xps/.fb2).")
    parser.add_argument("--title", default=None,
                        help="Course title for your own book (defaults to the filename).")
    parser.add_argument("--tier", default=None,
                        help="Academic tier label (default: Undergraduate).")
    parser.add_argument("--course-id", default=None,
                        help="Explicit course_id (default: custom_<slug of title>).")
    parser.add_argument("--source", default="physics", choices=list(BOOKS.keys()),
                        help="Which bundled textbook to divide (ignored with --file).")
    parser.add_argument("--llm", action="store_true",
                        help="Enrich theory with the local fine-tuned Llama (JSON mode). "
                             "Offline deterministic skeleton by default.")
    parser.add_argument("--max-chapters", type=int, default=None,
                        help="Limit Llama enrichment to the first N chapters; the rest "
                             "keep the deterministic grounded skeleton.")
    parser.add_argument("--enrich", type=int, default=None, metavar="N",
                        help="Alias of --max-chapters: enrich only the first N chapters.")
    parser.add_argument("--enrich-chapters", default=None, metavar="SPEC",
                        help="Exact chapters to enrich, e.g. '10', '1-10', '1,3,5-8'. "
                             "Everything else keeps the grounded skeleton.")
    parser.add_argument("--resume", action="store_true",
                        help="Skip chapters that already have Llama theory "
                             "(continue a partial build without redoing work).")
    parser.add_argument("--no-cards", action="store_true",
                        help="Skip the flashcard model call to roughly halve the "
                             "time per chapter.")
    parser.add_argument("--publish-every", type=int, default=1, metavar="N",
                        help="Re-publish the course after every N enriched chapters "
                             "(default 1) so an interrupted build keeps its work.")
    parser.add_argument("--subject", default=None, help="Override the subject label.")
    parser.add_argument("--description", default=None, help="Override course description.")
    parser.add_argument("--inspect", action="store_true",
                        help="Only print the inferred structure + division summary "
                             "(no theory synthesis, no publishing).")
    args = parser.parse_args()

    if args.file:
        divider = SmartBookDivider(path=args.file, title=args.title,
                                  subject=args.subject, tier=args.tier,
                                  course_id=args.course_id)
    else:
        divider = SmartBookDivider(args.source)

    if args.inspect:
        divider.parse_toc()
        chapters = divider.divide()
        print(f"\n[inspect] {len(chapters)} chapters:")
        for ch in chapters:
            labels = ", ".join(s["label"] for s in ch.get("section_texts", []))
            print(f"  U{ch.get('unit_index')} ch{ch.get('chapter_index')}: "
                  f"{ch.get('title')[:70]}  [{ch.get('sections_count')} sections]")
            if labels:
                print(f"      sections: {labels[:140]}")
        print("\n[inspect] nothing was published (remove --inspect to publish).")
        return

    result = divider.run(use_llm=args.llm,
                         max_chapters=args.enrich or args.max_chapters,
                         subject_override=args.subject,
                         description=args.description,
                         enrich_chapters=args.enrich_chapters,
                         resume=args.resume,
                         include_cards=not args.no_cards,
                         publish_every=max(1, args.publish_every))
    coverage = result.get("theory_coverage") or {}
    print(f"\n[DONE] {result['course_id']} is live with {result['chapters']} chapters "
          f"(theory mode: {result['mode']}).")
    if coverage:
        enriched = coverage.get("enriched_count", 0)
        total = coverage.get("chapters_total", 0)
        print(f"[DONE] Theory: {enriched}/{total} chapters Llama-enriched.")
        if not coverage.get("complete"):
            source_arg = f'--file "{args.file}"' if args.file else f"--source {args.source}"
            print(f"[DONE] The rest use the grounded deterministic skeleton. Enrich "
                  f"more any time with:\n"
                  f"       python divide_book.py {source_arg} --llm --resume "
                  f"--enrich-chapters \"1-{total}\"")


if __name__ == "__main__":
    main()
