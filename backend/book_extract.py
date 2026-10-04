"""
================================================================================
 Learning Companion — High-Performance Book Extraction Engine
================================================================================

Extracts pages, outline / bookmarks, printed page numbers, and running headers
from PDF documents using PyMuPDF (fitz) with pypdf fallback.
================================================================================
"""

from __future__ import annotations

import io
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, List, Optional, Set, Tuple

try:
    import pymupdf
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    import pypdf
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False


# --------------------------------------------------------------------------- #
# Data structures
# --------------------------------------------------------------------------- #
@dataclass
class PageText:
    """Single extracted page of a book."""
    page_index: int       # 1-based PDF index
    text: str
    printed_page: Optional[int] = None   # detected printed page number if available


@dataclass
class OutlineEntry:
    """Bookmark / outline entry from embedded PDF metadata."""
    level: int            # 1-based hierarchy level (1 = top level / chapter)
    title: str
    page: int             # 1-based PDF page index


@dataclass
class ExtractedBook:
    """Full extraction result for a document."""
    pages: List[PageText] = field(default_factory=list)
    outline: List[OutlineEntry] = field(default_factory=list)
    running_headers: Set[str] = field(default_factory=set)

    @property
    def text(self) -> str:
        """Full plain text of all pages joined by double newlines."""
        return "\n\n".join(p.text for p in self.pages)

    @property
    def total_pages(self) -> int:
        return len(self.pages)


# --------------------------------------------------------------------------- #
# Helper functions
# --------------------------------------------------------------------------- #
_WS_RE = re.compile(r"[ \t]{2,}")
_DIGIT_RUN_RE = re.compile(r"\d+")


def normalize_line(line: str) -> str:
    """Digit-normalized line shape (e.g. '1.1 • Computer Science 21' -> '#.# • computer science #')."""
    s = _WS_RE.sub(" ", (line or "").strip())
    return _DIGIT_RUN_RE.sub("#", s).lower()


def detect_printed_page(lines: List[str], total_pages: Optional[int] = None) -> Optional[int]:
    """Detects printed page number from header or footer lines on a page."""
    # Check if page is copyright / front matter / metadata
    is_meta_page = any(
        re.search(r"\b(?:contents|table of contents|isbn|publication year|rice university|all rights reserved|creative commons)\b", l, re.I)
        for l in lines[:10]
    )
    if is_meta_page:
        return None

    candidates = lines[:3] + lines[-3:]
    max_page = total_pages + 50 if total_pages else 3000

    # Direct number on its own line
    for line in candidates:
        s = line.strip()
        m = re.match(r"^(?:page\s*)?(\d{1,4})$", s, re.IGNORECASE)
        if m:
            val = int(m.group(1))
            if 1 <= val <= max_page:
                return val

    # Number at edge of header/footer line
    for line in candidates:
        s = line.strip()
        if re.search(r"openstax|creative commons|license|attribution|isbn", s, re.I):
            continue
        m1 = re.match(r"^(\d{1,4})\s{2,}", s)
        if m1:
            val = int(m1.group(1))
            if 1 <= val <= max_page:
                return val
        m2 = re.search(r"\s{2,}(\d{1,4})$", s)
        if m2:
            val = int(m2.group(1))
            if 1 <= val <= max_page:
                return val
        m3 = re.search(r"[\u2022\u00b7\u00f2]\s*(\d{1,4})$", s)
        if m3:
            val = int(m3.group(1))
            if 1 <= val <= max_page:
                return val
    return None


def detect_running_headers(pages: List[PageText], min_repeat: int = 5) -> Set[str]:
    """Finds digit-normalized line shapes repeated >= min_repeat times across pages."""
    counts: Counter = Counter()
    for p in pages:
        seen_on_page: Set[str] = set()
        for raw in p.text.split("\n"):
            s = raw.strip()
            if not (8 <= len(s) <= 90):
                continue
            if not re.search(r"[A-Za-z]{3,}", s) or not _DIGIT_RUN_RE.search(s):
                continue
            norm = normalize_line(s)
            if norm not in seen_on_page:
                seen_on_page.add(norm)
                counts[norm] += 1
    return {form for form, cnt in counts.items() if cnt >= min_repeat}


def _extract_pypdf_outline(reader: Any) -> List[OutlineEntry]:
    """Recursively extracts outlines from pypdf reader."""
    entries: List[OutlineEntry] = []

    def _recurse(items: Any, level: int = 1) -> None:
        for item in items:
            if isinstance(item, list):
                _recurse(item, level + 1)
            else:
                try:
                    title = getattr(item, "title", "")
                    if hasattr(reader, "get_destination_page_number"):
                        dest = reader.get_destination_page_number(item)
                        page_num = (dest + 1) if (dest is not None and dest >= 0) else 1
                    else:
                        page_num = 1
                    if title and page_num > 0:
                        entries.append(OutlineEntry(level=level, title=title.strip(), page=page_num))
                except Exception:
                    pass

    if hasattr(reader, "outline") and reader.outline:
        _recurse(reader.outline, 1)
    return entries


# --------------------------------------------------------------------------- #
# Main extraction API
# --------------------------------------------------------------------------- #
# --------------------------------------------------------------------------- #
# Main extraction API
# --------------------------------------------------------------------------- #
def extract_pdf(source: Any) -> ExtractedBook:
    """
    Extracts structured pages, bookmarks outline, and running headers from a PDF.
    
    Accepts a file path string or raw PDF bytes.
    Tries PyMuPDF (fitz) first for maximum performance, with graceful fallback to pypdf.
    """
    is_bytes = isinstance(source, (bytes, bytearray))
    if not is_bytes:
        if not isinstance(source, str) or not os.path.exists(source):
            raise FileNotFoundError(f"PDF file not found: {source}")

    # 1. Primary Engine: PyMuPDF (fitz)
    if PYMUPDF_AVAILABLE:
        try:
            doc = pymupdf.open(stream=source, filetype="pdf") if is_bytes else pymupdf.open(source)
            with doc:
                total_pages = len(doc)
                pages: List[PageText] = []
                for idx in range(total_pages):
                    page = doc[idx]
                    text = page.get_text("text") or ""
                    lines = [l.strip() for l in text.split("\n") if l.strip()]
                    printed_page = detect_printed_page(lines, total_pages=total_pages)
                    pages.append(PageText(page_index=idx + 1, text=text, printed_page=printed_page))

                toc = doc.get_toc() or []
                outline: List[OutlineEntry] = [
                    OutlineEntry(level=int(item[0]), title=str(item[1]).strip(), page=int(item[2]))
                    for item in toc
                    if len(item) >= 3 and int(item[2]) > 0
                ]

                running_headers = detect_running_headers(pages)
                return ExtractedBook(pages=pages, outline=outline, running_headers=running_headers)
        except Exception as e:
            if not PYPDF_AVAILABLE:
                raise RuntimeError(f"PyMuPDF extraction failed and pypdf is unavailable: {e}")

    # 2. Secondary Engine: pypdf
    if PYPDF_AVAILABLE:
        try:
            reader = pypdf.PdfReader(io.BytesIO(source)) if is_bytes else pypdf.PdfReader(source)
            total_pages = len(reader.pages)
            pages = []
            for idx, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                lines = [l.strip() for l in text.split("\n") if l.strip()]
                printed_page = detect_printed_page(lines, total_pages=total_pages)
                pages.append(PageText(page_index=idx + 1, text=text, printed_page=printed_page))

            outline = _extract_pypdf_outline(reader)
            running_headers = detect_running_headers(pages)
            return ExtractedBook(pages=pages, outline=outline, running_headers=running_headers)
        except Exception as e:
            raise RuntimeError(f"pypdf extraction failed for {source if not is_bytes else '<bytes>'}: {e}")

    raise RuntimeError("Neither pymupdf nor pypdf is installed in the current environment.")
