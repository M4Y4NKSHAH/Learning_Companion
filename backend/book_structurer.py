"""
================================================================================
 Learning Companion — Book Structure Inference (book-agnostic)
================================================================================

Turns *any* user-supplied book into a structural plan before it is divided:

    pdf/epub/txt/md  ->  front-matter vs running text
                     ->  "what does a chapter heading look like here?"
                     ->  "what does a section heading look like here?"
                     ->  "does this book group chapters into parts/units?"

Why this module exists
----------------------
The division engine must never assume one publisher's layout. Real user books
say `CHAPTER 4`, `Chapter 4: Cells`, `# Chapter 4`, `UNIT 3 - Mechanics`,
`Lesson 7`, `CHAPTER IV`, `Chapter Four`, `4. Cells`, or they have no headings
at all. So instead of hardcoding one regex, this module *scores* every plausible
heading pattern against the document and returns the best-supported plan, with
graceful degradation (size-balanced chunking) so ingestion never hard-fails.

Every inference is reported in `StructurePlan.notes` and
`StructurePlan.describe()` so the CLI/UI can show the user what was detected.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
_WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "twentyone": 21, "twentytwo": 22, "twentythree": 23,
    "twentyfour": 24, "twentyfive": 25, "twentysix": 26, "twentyseven": 27,
    "twentyeight": 28, "twentynine": 29, "thirty": 30, "thirtyone": 31,
    "thirtytwo": 32, "thirtythree": 33, "thirtyfour": 34, "thirtyfive": 35,
}
_WORD_RE_ALT = "|".join(sorted(_WORD_NUMBERS, key=len, reverse=True))

_PAGE_ONLY_RE = re.compile(r"^\s*(?:page\s*)?\d{1,4}\s*$", re.IGNORECASE)
_DIGIT_RUN_RE = re.compile(r"\d+")
_WS_RE = re.compile(r"[ \t]{2,}")
_DOTTED_LEADER_RE = re.compile(r"\.{2,}\s*\d{1,4}\s*$")


def roman_to_int(token: str) -> Optional[int]:
    """`XIV` -> 14. Returns None when the token is not a valid Roman numeral."""
    token = (token or "").strip().upper()
    if not token or any(ch not in _ROMAN_VALUES for ch in token):
        return None
    total, prev = 0, 0
    for ch in reversed(token):
        val = _ROMAN_VALUES[ch]
        total += -val if val < prev else val
        prev = max(prev, val)
    return total or None


def word_to_int(token: str) -> Optional[int]:
    """`Twenty Three` -> 23."""
    return _WORD_NUMBERS.get(re.sub(r"[^a-z]", "", (token or "").lower()))


def slugify(text: str, fallback: str = "book") -> str:
    """`College Physics 2e (OpenStax)` -> `college_physics_2e_openstax`."""
    slug = re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")
    return slug[:48] or fallback


def pretty_title_from_filename(path: str) -> str:
    """`Data Structures and Algorithms.pdf` -> `Data Structures and Algorithms`."""
    import os
    stem = os.path.splitext(os.path.basename(path or ""))[0]
    stem = re.sub(r"[_\-]+", " ", stem).strip()
    return re.sub(r"\s{2,}", " ", stem) or "Untitled Book"


# --------------------------------------------------------------------------- #
# Data containers
# --------------------------------------------------------------------------- #
@dataclass
class HeadingSpot:
    """One detected heading occurrence in the raw document."""
    pos: int
    number: int
    title: str = ""      # inline remainder of the heading line (may be "")
    line: str = ""       # the full heading line, stripped
    level: int = 1       # markdown level for hash-headings, else 1


@dataclass
class StructurePlan:
    """The inferred skeleton of a book — everything the divider needs."""
    chapter_kind: str = "none"
    chapter_matches: List[HeadingSpot] = field(default_factory=list)
    section_kind: str = "chunk"
    section_level: Optional[int] = None
    units: Optional[List[Dict[str, Any]]] = None
    unit_kind: str = "buckets"
    body_start: int = 0
    toc_detected: bool = False
    toc_count: int = 0
    confidence: float = 0.0
    running_forms: Set[str] = field(default_factory=set)
    notes: List[str] = field(default_factory=list)

    # ---------------------------------------------------------------- #
    def is_running_line(self, line: str) -> bool:
        """True for repeated running headers/footers and bare page numbers."""
        s = (line or "").strip()
        if not s:
            return False
        if _PAGE_ONLY_RE.match(s):
            return True
        return self.normalize_line(s) in self.running_forms

    @staticmethod
    def normalize_line(line: str) -> str:
        """Page numbers collapse to `#` so `12 Cells 45` == `13 Cells 46`."""
        s = _WS_RE.sub(" ", (line or "").strip())
        return _DIGIT_RUN_RE.sub("#", s).lower()

    def describe(self) -> str:
        ch = f"{len(self.chapter_matches)} chapters via '{self.chapter_kind}'"
        sec = (f"sections via '{self.section_kind}'"
               + (f" (markdown level {self.section_level})" if self.section_level else ""))
        units = (f"{len(self.units)} units via '{self.unit_kind}'" if self.units
                 else "units: automatic balanced buckets")
        lines = [
            f"chapter pattern : {ch}",
            f"section pattern : {sec}",
            f"unit strategy   : {units}",
            f"body starts at  : char {self.body_start}"
            + ("  (front-matter TOC skipped)" if self.toc_detected else ""),
            f"toc detected    : {'yes' if self.toc_detected else 'no'}"
            + (f" ({self.toc_count} entries)" if self.toc_count else ""),
            f"running-header forms suppressed: {len(self.running_forms)}",
            f"confidence      : {self.confidence:.2f}",
        ]
        if self.notes:
            lines.append("notes           : " + "; ".join(self.notes))
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Candidate heading patterns (scored, never assumed)
# --------------------------------------------------------------------------- #
def _chapter_candidates() -> List[Tuple[str, re.Pattern, str, bool]]:
    """`(kind, regex, number_style, is_unit_level)`.

    Every regex exposes group(1) = number token, group(2) = inline title.
    `number_style` is one of digits | roman | word | order | hash.
    """
    sep = r"[ \t]*[:.\-–—)\]]?[ \t]*"
    return [
        ("chapter_digits",
         re.compile(r"(?im)^[ \t]*(?:CHAP(?:TER|\.)?|CHAPTER)[ \t]+(\d{1,3})\b" + sep + r"(.*)$"),
         "digits", False),
        ("chapter_roman",
         re.compile(r"(?im)^[ \t]*(?:CHAP(?:TER|\.)?)[ \t]+([IVXLCDM]{1,7})\b" + sep + r"(.*)$"),
         "roman", False),
        ("chapter_word",
         re.compile(r"(?im)^[ \t]*(?:CHAP(?:TER|\.)?)[ \t]+(" + _WORD_RE_ALT + r")\b" + sep + r"(.*)$"),
         "word", False),
        ("unit_digits",
         re.compile(r"(?im)^[ \t]*(?:UNIT|PART|MODULE|BOOK|VOLUME)[ \t]+(\d{1,3})\b" + sep + r"(.*)$"),
         "digits", True),
        ("unit_roman",
         re.compile(r"(?im)^[ \t]*(?:UNIT|PART|MODULE|BOOK|VOLUME)[ \t]+([IVXLCDM]{1,7})\b" + sep + r"(.*)$"),
         "roman", True),
        ("lesson_digits",
         re.compile(r"(?im)^[ \t]*(?:LESSON|LECTURE|TOPIC|WEEK|SESSION|CLASS|DAY)[ \t]+(\d{1,3})\b" + sep + r"(.*)$"),
         "digits", False),
        ("hash_headings",
         re.compile(r"(?m)^(#{1,4})[ \t]*(.+?)[ \t]*#*[ \t]*$"),
         "hash", False),
        ("numbered_dot",
         re.compile(r"(?m)^[ \t]*(\d{1,3})\.[ \t]+([A-Z][^.\n]{2,80})$"),
         "digits", False),
        ("numbered_bare",
         re.compile(r"(?m)^[ \t]*(\d{1,3})[ \t]+([A-Z][A-Za-z0-9 ,'&\-–—:]{2,70}[A-Za-z0-9)\]\.])[ \t]*$"),
         "digits", False),
        ("titled_caps",
         re.compile(r"(?m)^[ \t]*([A-Z][A-Z0-9 ,'&\-–—:]{5,70})[ \t]*$"),
         "order", False),
    ]


def _section_patterns() -> List[Tuple[str, re.Pattern]]:
    """`(kind, regex)` where group(1) = parent number (when numeric)."""
    return [
        ("numdot",
         re.compile(r"(?m)^[ \t]*(\d{1,3})\.(\d{1,2})\b[ \t]*[:.\-–—]?[ \t]*([^\n]{2,90})$")),
        ("numdot_deep",
         re.compile(r"(?m)^[ \t]*(\d{1,3})\.(\d{1,2})\.(\d{1,2})\b[ \t]*[:.\-–—]?[ \t]*([^\n]{2,90})$")),
        ("dashdot",
         re.compile(r"(?m)^[ \t]*(\d{1,3})[ \t]*[-–—][ \t]*([^\n]{2,90})$")),
        ("letdot",
         re.compile(r"(?m)^[ \t]*([A-Z])[.)][ \t]+([^\n]{3,80})$")),
        ("shortline",
         re.compile(r"(?m)^[ \t]*([A-Z][A-Za-z0-9 ,'&\-–—]{3,70})[ \t]*$")),
    ]


GENERIC_BACKMATTER = (
    "summary", "chapter summary", "section summary", "key terms", "key concepts",
    "glossary", "review questions", "review exercises", "exercises", "problems",
    "problems and exercises", "problems & exercises", "conceptual questions",
    "discussion questions", "self-test", "self test", "further reading",
    "references", "bibliography", "index", "answers", "chapter review",
    "check your understanding", "critical thinking", "additional problems",
)

BOILERPLATE_SUBSTRINGS = (
    "senior contributing author", "senior contributing authors",
    "philanthropic support", "contents", "table of contents",
    "global issues in technology", "think it through", "link to learning",
    "industry spotlight", "concepts in practice", "technology in everyday life",
    "media", "student project", "chapter review", "chapter summary",
    "review questions", "key terms", "glossary", "index", "references",
    "solutions", "answers", "preface", "about the author", "about the authors",
    "openstax", "rice university", "isbn", "all rights reserved",
    "further reading", "conceptual questions", "brief contents",
    "learning objectives", "learning outcomes", "answer key", "try it",
    "solutions to", "answers to", "source:"
)


# --------------------------------------------------------------------------- #
# The structurer
# --------------------------------------------------------------------------- #
class BookStructurer:
    """Infers the skeleton of an arbitrary book. Stateless, offline, fast."""

    MIN_CHAPTERS = 3
    MAX_CHAPTERS = 120

    def __init__(self, text: str, hints: Optional[Dict[str, Any]] = None):
        self.text = text or ""
        self.hints = hints or {}
        self.notes: List[str] = []

    # ------------------------------------------------------------------ #
    # Orchestration
    # ------------------------------------------------------------------ #
    def plan(self) -> StructurePlan:
        plan = StructurePlan()
        if len(self.text.strip()) < 500:
            plan.notes.append("document too short for structural inference")
            return plan

        plan.toc_detected = self._toc_region_end() is not None

        scored = self._scan_chapters()
        if scored:
            best = max(scored, key=lambda c: c["score"])
            plan.chapter_kind = best["kind"]
            plan.chapter_matches = best["spots"]
            plan.confidence = round(best["score"], 3)
            plan.notes.append(
                f"'{best['kind']}' scored {best['score']:.2f} "
                f"(sequence {best['seq']:.2f}, spread {best['spread']:.2f}, "
                f"heading-quality {best['quality']:.2f}, n={len(best['spots'])})")
            for spot in plan.chapter_matches:
                if not spot.title:
                    spot.title = self.title_after(spot.pos)
        else:
            plan.chapter_kind = "none"
            plan.chapter_matches = self._size_balanced_spots(self.text)
            plan.notes.append("no chapter-like headings found -> size-balanced division")
            plan.confidence = 0.2

        plan.body_start = self._find_body_start(plan.chapter_matches, plan.chapter_kind)
        plan.toc_count = self._count_toc_entries(plan.body_start)
        self._detect_sections(plan)
        self._detect_units(plan)
        plan.running_forms = self._detect_running_forms()
        plan.notes.extend(self.notes)
        return plan

    # ------------------------------------------------------------------ #
    # Front matter / TOC region
    # ------------------------------------------------------------------ #
    def _toc_region_end(self) -> Optional[int]:
        """Char offset where the front-matter TOC ends, or None if there is none."""
        window = self.text[: max(6000, int(len(self.text) * 0.35))]
        hits = list(re.finditer(r"(?im)^[ \t]*(?:table of )?contents[ \t]*$", window))
        if not hits:
            return None
        offset = hits[0].end()
        last_toc_line: Optional[int] = None
        for line in window[offset:].split("\n")[:400]:
            stripped = line.strip()
            if stripped:
                looks_toc = bool(_DOTTED_LEADER_RE.search(stripped)) or bool(
                    re.search(r"\s\d{1,4}\s*$", stripped))
                if looks_toc:
                    last_toc_line = offset + len(line)
                elif last_toc_line is not None and len(stripped) > 120:
                    break
            offset += len(line) + 1
        return last_toc_line or hits[0].end()

    def _count_toc_entries(self, body_start: int) -> int:
        if not body_start:
            return 0
        front = self.text[:body_start]
        return sum(1 for ln in front.split("\n")
                   if _DOTTED_LEADER_RE.search(ln.strip())
                   or re.search(r"\s\d{1,4}\s*$", ln.strip()))

    def _find_body_start(self, spots: List[HeadingSpot], chapter_kind: str = "") -> int:
        """First chapter heading in the *running text* (TOC listing skipped)."""
        if chapter_kind == "none" or not spots:
            return self._toc_region_end() or 0
        ordered = sorted(spots, key=lambda s: s.pos)
        dense = self._is_dense_listing(ordered)
        body_like = [s for s, in_dense in zip(ordered, dense) if not in_dense]
        if len(body_like) >= self.MIN_CHAPTERS:
            return body_like[0].pos
        cluster = self._leading_toc_cluster(ordered)
        if cluster:
            after = ordered[len(cluster):]
            if after:
                return after[0].pos
        return ordered[0].pos

    def title_after(self, pos: int, max_lines: int = 4) -> str:
        """Title text for a bare heading line (e.g. `CHAPTER 4` -> next line)."""
        tail = self.text[pos:]
        newline = tail.find("\n")
        if newline == -1:
            return ""
        for raw in tail[newline + 1:].split("\n")[:max_lines]:
            s = raw.strip()
            if not s:
                continue
            if len(s) > 95 or _PAGE_ONLY_RE.match(s):
                return ""
            return re.sub(r"\s{2,}", " ", s)
        return ""

    def _size_balanced_spots(self, text: str, target_chars: int = 24000) -> List[HeadingSpot]:
        """Last-resort division: evenly sized prose blocks become 'parts'."""
        chunks = self.chunk_text(text, target_chars=target_chars, max_chunks=self.MAX_CHAPTERS)
        spots: List[HeadingSpot] = []
        cursor = 0
        for idx, chunk in enumerate(chunks, 1):
            found = text.find(chunk[:200], cursor) if chunk else -1
            pos = found if found != -1 else cursor
            cursor = pos + 1
            title = self.fallback_title(chunk) or f"Part {idx}"
            spots.append(HeadingSpot(pos=pos, number=idx, title=title,
                                     line=f"Part {idx}", level=1))
        return spots

    # ------------------------------------------------------------------ #
    # Heading scanning & scoring
    # ------------------------------------------------------------------ #
    @staticmethod
    def _to_number(token: str, style: str) -> Optional[int]:
        if style == "digits":
            return int(token) if token.isdigit() else None
        if style == "roman":
            return roman_to_int(token)
        if style == "word":
            return word_to_int(token)
        return None

    def _is_dense_listing(self, spots: List[HeadingSpot]) -> List[bool]:
        """Flags headings that sit inside a tightly packed TOC-style listing.

        Gaps between consecutive headings are sorted and the largest relative
        jump separates "listing" spacing from "chapter" spacing. A heading counts
        as a listing entry only when the headings on *both* sides are equally
        close (a real chapter heading is fenced by long stretches of prose). This
        is layout-based, so it works for PDFs, EPUB dumps and notes alike — and it
        catches books that print several stacked listings.
        """
        positions = [s.pos for s in spots]
        if len(positions) < 5:
            return [False] * len(positions)
        gaps = [b - a for a, b in zip(positions, positions[1:])]
        positive = sorted(g for g in gaps if g > 0)
        if len(positive) < 4:
            return [False] * len(positions)
        threshold, best_ratio = 0.0, 0.0
        for small, large in zip(positive, positive[1:]):
            ratio = large / small
            if ratio > best_ratio:
                best_ratio, threshold = ratio, (small * large) ** 0.5
        if best_ratio < 4:
            return [False] * len(positions)          # evenly spaced: real chapters

        # Single-linkage components over "tight" gaps: a listing is a run of 3+
        # headings chained by gaps well below the chapter spacing. Boundary
        # entries (last TOC line before the body) are caught by this too.
        flags = [False] * len(positions)
        run_start = 0
        for i, gap in enumerate(gaps):
            if gap >= threshold:
                if i - run_start + 1 >= 3:
                    for j in range(run_start, i + 1):
                        flags[j] = True
                run_start = i + 1
        if len(positions) - run_start >= 3:
            for j in range(run_start, len(positions)):
                flags[j] = True
        if sum(flags) > 0.8 * len(flags):            # almost everything: leave it alone
            return [False] * len(positions)
        return flags

    def _leading_toc_cluster(self, spots: List[HeadingSpot]) -> List[HeadingSpot]:
        """The leading run of headings packed tightly together — a TOC listing.

        Real chapters are far apart (thousands of characters); entries in a table
        of contents are adjacent lines. A cluster only counts when it is a strict
        prefix, so a book of genuinely short chapters is left alone.
        """
        spots = sorted(spots, key=lambda s: s.pos)
        if len(spots) < 4:
            return []
        tight = max(400, int(len(self.text) * 0.005))
        end = 1
        for i in range(1, len(spots)):
            if spots[i].pos - spots[i - 1].pos <= tight:
                end = i + 1
            else:
                break
        return spots[:end] if 3 <= end < len(spots) else []

    def _strip_front_matter_duplicates(self, spots: List[HeadingSpot]) -> List[HeadingSpot]:
        """A heading printed both in a front-matter listing and in the running text
        is a TOC entry; the running-text occurrence is the real chapter.

        Two signals are used, in order of reliability:
          1. spacing — headings chained by gaps far below the book's chapter
             spacing form a listing run (`_is_dense_listing`); real chapters stay.
          2. layout fallback — a leading run of tightly packed headings is treated
             as a TOC listing for books whose spacing is ambiguous.
        Chapter numbers may legitimately repeat in the body (books that restart
        numbering per unit), so duplicates are never pruned globally.
        """
        spots = sorted(spots, key=lambda s: s.pos)
        if len(spots) < 4:
            return spots

        dense = self._is_dense_listing(spots)
        body_like = [s for s, in_dense in zip(spots, dense) if not in_dense]
        if len(body_like) >= self.MIN_CHAPTERS:
            body_numbers = {s.number for s in body_like}
            kept: List[HeadingSpot] = []
            seen: Set[int] = set()
            for spot in reversed(spots):
                if spot.number in body_numbers or spot.number in seen:
                    continue
                seen.add(spot.number)
                kept.append(spot)
            return sorted(body_like + kept, key=lambda s: s.pos)

        cluster = self._leading_toc_cluster(spots)
        if not cluster:
            return spots
        rest = spots[len(cluster):]
        rest_numbers = {s.number for s in rest}
        kept_front: List[HeadingSpot] = []
        seen = set()
        # Walk the cluster backwards: for a chapter that has no body occurrence,
        # the last TOC-window occurrence is the one closest to the real heading.
        for spot in reversed(cluster):
            if spot.number in rest_numbers or spot.number in seen:
                continue
            seen.add(spot.number)
            kept_front.append(spot)
        return sorted(rest + kept_front, key=lambda s: s.pos)

    @staticmethod
    def _sequence_score(spots: List[HeadingSpot]) -> float:
        """Share of chapter numbers that form a +1 consecutive run."""
        if len(spots) < 2:
            return 0.0
        numbers = [s.number for s in spots]
        best = run = 1
        for prev, cur in zip(numbers, numbers[1:]):
            run = run + 1 if cur == prev + 1 else 1
            best = max(best, run)
        return best / len(numbers)

    @staticmethod
    def _heading_quality(spots: List[HeadingSpot], style: str) -> float:
        if not spots:
            return 0.0
        total = 0.0
        for spot in spots:
            title = spot.title
            if title:
                total += 1.0 if 3 <= len(title) <= 85 else 0.4
            else:
                total += 0.85 if style in ("digits", "roman", "word") else 0.2
        return total / len(spots)

    def _scan_chapters(self) -> List[Dict[str, Any]]:
        """Scores every chapter-shaped heading pattern against this document.

        Two passes: explicit numbered/keyword patterns run first and *claim* the
        lines they match; loose, unnumbered patterns (# headings, ALL-CAPS lines)
        then run without those lines, so a generic pattern can never hijack a
        book that numbers its chapters.
        """
        candidates = _chapter_candidates()
        results: List[Dict[str, Any]] = []
        claimed: Set[str] = set()

        for kind, regex, style, is_unit in candidates:
            if style == "order":
                continue
            if kind == "hash_headings":
                continue
            spots = self._strip_front_matter_duplicates(self._spots_from_regex(regex, style))
            if not (self.MIN_CHAPTERS <= len(spots) <= self.MAX_CHAPTERS):
                continue
            claimed.update(StructurePlan.normalize_line(s.line) for s in spots)
            scored = self._score_candidate(kind, style, is_unit, spots)
            if scored:
                results.append(scored)

        for kind, regex, style, is_unit in candidates:
            if kind == "hash_headings":
                spots = self._hash_spots(regex)
                if self.MIN_CHAPTERS <= len(spots) <= self.MAX_CHAPTERS:
                    scored = self._score_candidate(kind, style, is_unit, spots)
                    if scored:
                        results.append(scored)

        has_explicit = any(r["kind"] in ("chapter_digits", "chapter_roman", "chapter_word", "numbered_dot", "hash_headings") for r in results)
        if not has_explicit:
            grouped_spots = self._strip_front_matter_duplicates(self._scan_grouped_numdot())
            if grouped_spots and (self.MIN_CHAPTERS <= len(grouped_spots) <= self.MAX_CHAPTERS):
                claimed.update(StructurePlan.normalize_line(s.line) for s in grouped_spots)
                scored = self._score_candidate("grouped_numdot", "digits", False, grouped_spots)
                if scored:
                    results.append(scored)

        for kind, regex, style, is_unit in candidates:
            if style == "order":
                spots = [s for s in self._spots_from_regex(regex, style)
                         if StructurePlan.normalize_line(s.line) not in claimed]
                for idx, spot in enumerate(spots, 1):
                    spot.number = idx
                if not (self.MIN_CHAPTERS <= len(spots) <= self.MAX_CHAPTERS):
                    continue
                scored = self._score_candidate(kind, style, is_unit, spots)
                if scored:
                    results.append(scored)
        return results

    def _scan_grouped_numdot(self) -> List[HeadingSpot]:
        """Detects major chapters by clustering subsection headings (1.1, 1.2, ..., 2.1, 2.2)."""
        sec_pattern = re.compile(r'(?m)^[ \t]*#{0,4}[ \t]*([1-9]\d*)\.([0-9]+)[ \t]+([A-Z][^\n]{3,80})')
        matches = list(sec_pattern.finditer(self.text))
        if len(matches) < 4:
            return []

        by_ch: Dict[int, List[Tuple[int, str]]] = {}
        for m in matches:
            ch_num = int(m.group(1))
            raw_title = m.group(3).strip()
            clean_title = re.sub(r'\s+\d{1,4}$', '', raw_title).strip()
            if any(bp in clean_title.lower() for bp in BOILERPLATE_SUBSTRINGS):
                continue
            by_ch.setdefault(ch_num, []).append((m.start(), clean_title))

        sorted_chs = sorted(by_ch.keys())
        if len(sorted_chs) < self.MIN_CHAPTERS or len(sorted_chs) > self.MAX_CHAPTERS:
            return []

        ch_run = sum(1 for p, c in zip(sorted_chs, sorted_chs[1:]) if c == p + 1)
        if ch_run < len(sorted_chs) * 0.4:
            return []

        spots: List[HeadingSpot] = []
        for ch_num in sorted_chs:
            sec_list = by_ch[ch_num]
            body_occ = [x for x in sec_list if x[0] > 10000]
            first_pos, first_title = body_occ[0] if (body_occ and len(sec_list) > len(body_occ)) else sec_list[0]

            pre_text = self.text[max(0, first_pos - 800):first_pos]
            parent_m = re.search(r'(?:^|\n)[ \t]*#{1,2}[ \t]+([A-Z][^\n]{3,80})\s*$', pre_text)
            title = parent_m.group(1).strip() if parent_m else first_title

            spots.append(HeadingSpot(
                pos=first_pos,
                number=ch_num,
                title=f"Chapter {ch_num}: {title}",
                line=f"Chapter {ch_num}: {title}",
                level=1
            ))
        return sorted(spots, key=lambda s: s.pos)

    def _spots_from_regex(self, regex: re.Pattern, style: str) -> List[HeadingSpot]:
        spots: List[HeadingSpot] = []
        for idx, m in enumerate(regex.finditer(self.text)):
            line = m.group(0).strip()
            if len(line) > 110:
                continue
            line_low = line.lower()
            if any(bp in line_low for bp in BOILERPLATE_SUBSTRINGS):
                continue
            if style == "order":
                number, title = idx + 1, m.group(1).strip()
                if any(bp in title.lower() for bp in BOILERPLATE_SUBSTRINGS):
                    continue
            else:
                number = self._to_number(m.group(1), style)
                if number is None:
                    continue
                if style == "digits" and not (1 <= number <= 200):
                    continue
                title = (m.group(2) or "").strip()
                if not title:
                    cand_title = self.title_after(m.start())
                    if cand_title and any(bp in cand_title.lower() for bp in BOILERPLATE_SUBSTRINGS):
                        continue
                elif any(bp in title.lower() for bp in BOILERPLATE_SUBSTRINGS):
                    continue
            spots.append(HeadingSpot(pos=m.start(), number=number, title=title, line=line))
        return sorted(spots, key=lambda s: s.pos)

    # Bumped for patterns that carry an explicit, unambiguous publisher signal.
    _SPECIFICITY = {
        "grouped_numdot": 0.08,
        "chapter_digits": 0.05, "chapter_roman": 0.05, "chapter_word": 0.05,
        "unit_digits": 0.03, "unit_roman": 0.03, "lesson_digits": 0.03,
        "hash_headings": 0.02, "numbered_dot": 0.02, "numbered_bare": 0.0,
        "titled_caps": -0.25,
    }

    def _score_candidate(self, kind: str, style: str, is_unit: bool,
                          spots: List[HeadingSpot]) -> Optional[Dict[str, Any]]:
        if not spots:
            return None
        seq = 0.0 if style == "order" else self._sequence_score(spots)
        spread = (spots[-1].pos - spots[0].pos) / max(1, len(self.text))
        quality = self._heading_quality(spots, style)
        population = min(len(spots), 12) / 12.0
        score = (0.40 * seq + 0.22 * spread + 0.23 * quality + 0.15 * population
                 + self._SPECIFICITY.get(kind, 0.0))
        if is_unit:
            score -= 0.08
        if style == "order" and spread < 0.4:
            score -= 0.15        # a heading-less book is better handled by chunking
        return {"kind": kind, "style": style, "is_unit": is_unit, "spots": spots,
                "score": max(score, 0.0), "seq": seq, "spread": spread,
                "quality": quality}


    def _hash_spots(self, regex: re.Pattern) -> List[HeadingSpot]:
        """Picks the markdown heading level that behaves like chapters."""
        bucket: Dict[int, List[HeadingSpot]] = {}
        for m in regex.finditer(self.text):
            level = len(m.group(1))
            title = m.group(2).strip()
            if not title or len(title) > 110:
                continue
            bucket.setdefault(level, []).append(
                HeadingSpot(pos=m.start(), number=0, title=title,
                            line=m.group(0).strip(), level=level))
        if not bucket:
            return []
        # Chapters use the shallowest level that is populated enough to be a
        # division of the book (deeper levels are usually the sections).
        eligible = [lv for lv in sorted(bucket) if len(bucket[lv]) >= self.MIN_CHAPTERS]
        level = eligible[0] if eligible else sorted(bucket, key=lambda lv: (-len(bucket[lv]), lv))[0]
        spots = sorted(bucket[level], key=lambda s: s.pos)
        # A lone shallow heading is the document title, not a chapter.
        if eligible and len(bucket[level]) == 1:
            level = sorted(bucket, key=lambda lv: (-len(bucket[lv]), lv))[0]
            spots = sorted(bucket[level], key=lambda s: s.pos)
        if len(spots) > self.MIN_CHAPTERS and self._is_document_title(spots[0]):
            self.notes.append("leading '# title' heading treated as the book title")
            spots = spots[1:]
        for idx, spot in enumerate(spots, 1):
            spot.number = idx
        self.notes.append(f"markdown heading level {level} used for chapters")
        return spots

    def _is_document_title(self, spot: HeadingSpot) -> bool:
        """True for an `# My Book Title` line that sits above every chapter."""
        if spot.pos > 200:
            return False
        if re.search(r"(chapter|unit|part|lesson|module|lecture|week|\d)", spot.title, re.I):
            return False
        return len(spot.title) <= 90

    # ------------------------------------------------------------------ #
    # Section-level inference
    # ------------------------------------------------------------------ #
    def _chapter_spans(self, plan: StructurePlan) -> List[Tuple[int, int, int]]:
        """`(chapter_number, start, end)` spans derived from the chapter spots."""
        spots = plan.chapter_matches
        spans: List[Tuple[int, int, int]] = []
        for i, spot in enumerate(spots):
            end = spots[i + 1].pos if i + 1 < len(spots) else len(self.text)
            spans.append((spot.number, spot.pos, max(end, spot.pos + 1)))
        return spans

    def _score_section_kind(self, kind: str, regex: re.Pattern,
                            spans: List[Tuple[int, int, int]]) -> float:
        counts: List[int] = []
        for num, start, end in spans:
            body = self.text[start:end]
            found = 0
            for m in regex.finditer(body):
                if kind in ("numdot", "numdot_deep"):
                    parent = self._to_number(m.group(1), "digits")
                    if parent != num:
                        continue
                found += 1
            counts.append(found)
        if not counts:
            return 0.0
        good = sum(1 for c in counts if 2 <= c <= 15) / len(counts)
        avg = sum(counts) / len(counts)
        return 0.7 * good + 0.3 * min(avg, 8) / 8.0

    def _detect_sections(self, plan: StructurePlan) -> None:
        spans = self._chapter_spans(plan)
        if len(spans) < 2:
            plan.section_kind = "chunk"
            self.notes.append("single chapter -> section chunking")
            return
        if plan.chapter_kind == "hash_headings":
            level = plan.chapter_matches[0].level + 1
            if len(plan.chapter_matches) >= 2 and self._hash_section_yield(spans, level) >= 0.6:
                plan.section_kind = "hash_headings"
                plan.section_level = level
                self.notes.append(f"markdown level {level} used for sections")
                return
        # Numbered headings are validated against the chapter number, so they
        # outrank loose patterns (which only need a short, title-cased line).
        specificity = {"numdot": 0.10, "numdot_deep": 0.07, "dashdot": 0.02,
                       "letdot": 0.0, "shortline": -0.18}
        best_kind, best_score, raw_best = "chunk", 0.0, 0.0
        for kind, regex in _section_patterns():
            raw = self._score_section_kind(kind, regex, spans)
            score = raw + specificity.get(kind, 0.0)
            if score > best_score:
                best_kind, best_score, raw_best = kind, score, raw
        if best_kind != "chunk" and raw_best >= 0.6:
            plan.section_kind = best_kind
            self.notes.append(f"section pattern '{best_kind}' scored {raw_best:.2f}")
        else:
            plan.section_kind = "chunk"
            self.notes.append("no reliable section headings -> size-balanced section chunks")

    def _hash_section_yield(self, spans: List[Tuple[int, int, int]], level: int) -> float:
        prefix = "#" * level
        rx = re.compile(r"(?m)^[ \t]*" + re.escape(prefix) + r"[ \t]*\S")
        counts = [len(rx.findall(self.text[start:end])) for _n, start, end in spans]
        if not counts:
            return 0.0
        return sum(1 for c in counts if 2 <= c <= 15) / len(counts)

    def section_starts(self, body: str, parent_num: int,
                       plan: StructurePlan) -> List[Tuple[int, str, str]]:
        """Heading line indexes inside a chapter body: `(line_index, label, title)`.

        Uses the pattern family the structurer selected for this book, so books
        that number sections `3.4`, dash them `3 - Title`, letter them `A. Title`
        or leave them unnumbered all produce a usable study map.
        """
        if plan.section_kind in ("chunk", "none"):
            return []
        lines = body.split("\n")
        out: List[Tuple[int, str, str]] = []

        if plan.section_kind == "hash_headings":
            prefix = "#" * (plan.section_level or 2)
            rx = re.compile(r"^[ \t]*" + re.escape(prefix) + r"[ \t]*(.+?)[ \t]*#*[ \t]*$")
            for i, ln in enumerate(lines):
                m = rx.match(ln)
                if not m:
                    continue
                title = m.group(1).strip()
                if len(title) < 3:
                    continue
                out.append((i, f"{parent_num}.{len(out) + 1}", title))
            return out

        regex = dict(_section_patterns())[plan.section_kind]
        numbered = plan.chapter_kind not in ("hash_headings", "titled_caps", "none")
        for i, ln in enumerate(lines):
            stripped = ln.strip()
            if not stripped or len(stripped) > 110:
                continue
            m = regex.match(stripped)
            if not m:
                continue
            if plan.section_kind in ("numdot", "numdot_deep"):
                parent = self._to_number(m.group(1), "digits")
                if parent is None or (numbered and parent != parent_num):
                    continue
                title = m.group(3).strip()
                label = f"{parent}.{m.group(2)}"
            elif plan.section_kind == "dashdot":
                title = m.group(2).strip()
                label = f"{parent_num}.{len(out) + 1}"
            elif regex.groups > 1:
                title = m.group(2).strip()
                label = f"{parent_num}.{len(out) + 1}"
            else:
                title = m.group(1).strip()
                label = f"{parent_num}.{len(out) + 1}"
            if len(title) < 3 or not re.search(r"[A-Za-z]{3,}", title):
                continue
            out.append((i, label, title))
        return out

    # ------------------------------------------------------------------ #
    # Chunking fallback (books with no headings at all)
    # ------------------------------------------------------------------ #
    @staticmethod
    def chunk_text(text: str, target_chars: int = 3000, max_chunks: int = 10) -> List[str]:
        """Groups a heading-less text into size-balanced blocks at paragraph
        boundaries (sentence boundaries as a last resort)."""
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text or "") if p.strip()]
        if not paragraphs:
            return []
        if len(paragraphs) == 1:
            paragraphs = [s.strip() for s in re.split(r"(?<=[.!?])\s+", paragraphs[0])
                          if s.strip()]
        chunks: List[str] = []
        buf: List[str] = []
        size = 0
        for para in paragraphs:
            buf.append(para)
            size += len(para) + 1
            if size >= target_chars and len(chunks) < max_chunks - 1:
                chunks.append("\n".join(buf))
                buf, size = [], 0
        if buf:
            chunks.append("\n".join(buf))
        return chunks[:max_chunks]

    @staticmethod
    def fallback_title(chunk: str, max_words: int = 8) -> str:
        """Readable placeholder title for a heading-less chunk."""
        first = re.split(r"(?<=[.:!?])\s|\n", (chunk or "").strip())[0] or ""
        words = re.sub(r"\s+", " ", first).strip().strip(".:;,").split(" ")
        title = " ".join(words[:max_words]).strip()
        return title if len(title) >= 8 else ""

    # ------------------------------------------------------------------ #
    # Unit-level inference
    # ------------------------------------------------------------------ #
    def _detect_units(self, plan: StructurePlan) -> None:
        """Reuses real PART/UNIT/MODULE divisions when the book declares them."""
        plan.unit_kind = "buckets"
        if not plan.chapter_matches:
            return
        # Ordered, not keyed by number: books that restart numbering per unit
        # legitimately reuse chapter numbers inside each unit.
        chapter_spots = sorted(plan.chapter_matches, key=lambda s: s.pos)
        for kind, regex, style, is_unit in _chapter_candidates():
            if not is_unit:
                continue
            marks: List[Tuple[int, int, str]] = []
            for m in regex.finditer(self.text):
                line = m.group(0).strip()
                if _DOTTED_LEADER_RE.search(line):
                    continue
                if any(bp in line.lower() for bp in BOILERPLATE_SUBSTRINGS):
                    continue
                num = self._to_number(m.group(1), style)
                if num is None:
                    continue
                title = (m.group(2) or "").strip() or self.title_after(m.start())
                if not title or title.startswith((",", ";", ".")) or title.endswith((",", ";")):
                    continue
                if title[0].islower():
                    continue
                if any(bp in title.lower() for bp in BOILERPLATE_SUBSTRINGS):
                    continue
                marks.append((m.start(), num, title))
            marks.sort(key=lambda t: t[0])
            if len(marks) < 2:
                continue
            units: List[Dict[str, Any]] = []
            for i, (pos, num, name) in enumerate(marks):
                end = marks[i + 1][0] if i + 1 < len(marks) else len(self.text)
                members = [s for s in chapter_spots if pos <= s.pos < end]
                if not members:
                    continue
                units.append({"unit": len(units) + 1,
                              "name": name or f"{kind.split('_')[0].title()} {num}",
                              "chapters": [s.number for s in members],
                              "start": pos, "end": end})
            if len(units) >= 2:
                plan.units = units
                plan.unit_kind = kind
                self.notes.append(f"declared units detected via '{kind}' ({len(units)})")
                return

    # ------------------------------------------------------------------ #
    # Noise (running headers/footers) detection
    # ------------------------------------------------------------------ #
    def _detect_running_forms(self) -> Set[str]:
        """Finds line shapes that repeat with a page number: real running headers.

        A line only qualifies when its digit-normalized form appears 5+ times,
        which keeps legitimate repeated prose out of the suppression list.
        """
        counts: Dict[str, int] = {}
        for raw in self.text.split("\n"):
            s = raw.strip()
            if not (8 <= len(s) <= 90):
                continue
            if not re.search(r"[A-Za-z]{3,}", s) or not _DIGIT_RUN_RE.search(s):
                continue
            form = StructurePlan.normalize_line(s)
            counts[form] = counts.get(form, 0) + 1
        forms = {form for form, count in counts.items() if count >= 5}
        if forms:
            self.notes.append(f"{len(forms)} repeated running-header/footer form(s) suppressed")
        return forms





