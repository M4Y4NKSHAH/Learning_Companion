import io
import os
import re
from typing import List, Dict, Any, Optional

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


class MaterialParser:
    """
    Enterprise Document Parser.
    Extracts, cleans, and structures raw content from PDFs, Markdown, and Plain Text files
    into standardized semantic sections and chunks for RAG vectorization and LLM theory processing.
    Equipped with PyMuPDF high-speed extraction engine and pypdf fallback.
    """

    @staticmethod
    def extract_text_from_pdf_bytes(pdf_bytes: bytes, max_pages: Optional[int] = None) -> str:
        """Extracts text content from in-memory PDF binary stream with high speed & error tolerance."""
        extracted_pages = []

        # 1. Primary High-Speed Engine: PyMuPDF (fitz)
        if PYMUPDF_AVAILABLE:
            try:
                doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
                total_pages = len(doc)
                page_limit = min(total_pages, max_pages) if (max_pages and max_pages > 0) else total_pages
                for idx in range(page_limit):
                    try:
                        page = doc.load_page(idx)
                        text = page.get_text("text").strip()
                        if text:
                            extracted_pages.append(f"--- Page {idx + 1} ---\n{text}")
                    except Exception as pe:
                        print(f"[PyMuPDF] Skipping page {idx+1}: {pe}")
                if extracted_pages:
                    return "\n\n".join(extracted_pages)
            except Exception as me:
                print(f"[PyMuPDF] Stream extraction error: {me}. Falling back to pypdf.")

        # 2. Secondary Engine: pypdf
        if PYPDF_AVAILABLE:
            pdf_file = io.BytesIO(pdf_bytes)
            try:
                reader = pypdf.PdfReader(pdf_file)
            except Exception as e:
                raise ValueError(f"Unable to parse PDF stream: {str(e)}")

            total_pages = len(reader.pages)
            for idx, page in enumerate(reader.pages):
                if max_pages and max_pages > 0 and idx >= max_pages:
                    break
                try:
                    text = page.extract_text() or ""
                    text = text.strip()
                    if text:
                        extracted_pages.append(f"--- Page {idx + 1} ---\n{text}")
                except Exception as e:
                    print(f"[pypdf] Skipping page {idx + 1}: {e}")
                    
            if extracted_pages:
                return "\n\n".join(extracted_pages)

        if not extracted_pages:
            raise RuntimeError("Neither PyMuPDF nor pypdf could extract readable text from this PDF file.")

        return "\n\n".join(extracted_pages)

    @staticmethod
    def extract_text_from_document_bytes(file_bytes: bytes, filename: str = "", max_pages: Optional[int] = None) -> str:
        """Extracts text content from in-memory binary stream (PDF, EPUB, MOBI, etc.) with high speed."""
        ext = os.path.splitext(filename)[1].lower().lstrip(".") if filename else "pdf"
        extracted_pages = []

        if PYMUPDF_AVAILABLE:
            try:
                fitz_type = ext if ext in ["pdf", "epub", "mobi", "xps", "fb2"] else "pdf"
                doc = pymupdf.open(stream=file_bytes, filetype=fitz_type)
                total_pages = len(doc)
                page_limit = min(total_pages, max_pages) if (max_pages and max_pages > 0) else total_pages
                for idx in range(page_limit):
                    try:
                        page = doc.load_page(idx)
                        text = page.get_text("text").strip()
                        if text:
                            extracted_pages.append(f"--- Section/Page {idx + 1} ---\n{text}")
                    except Exception:
                        continue
                if extracted_pages:
                    return "\n\n".join(extracted_pages)
            except Exception as me:
                print(f"[PyMuPDF] Stream extraction error for {filename}: {me}. Attempting fallback.")

        # Fallback for PDF
        if ext == "pdf" and PYPDF_AVAILABLE:
            try:
                reader = pypdf.PdfReader(io.BytesIO(file_bytes))
                pages_to_read = reader.pages[:max_pages] if (max_pages and max_pages > 0) else reader.pages
                for idx, page in enumerate(pages_to_read):
                    text = (page.extract_text() or "").strip()
                    if text:
                        extracted_pages.append(f"--- Page {idx + 1} ---\n{text}")
                if extracted_pages:
                    return "\n\n".join(extracted_pages)
            except Exception as pe:
                print(f"[pypdf] Fallback failed: {pe}")

        # Plain text fallback
        try:
            return file_bytes.decode("utf-8", errors="replace")
        except Exception:
            raise RuntimeError(f"Unable to parse document '{filename}'. Supported formats: PDF, EPUB, MOBI, TXT, MD.")

    @staticmethod
    def extract_book(source: Any, filename: str = ""):
        """Extracts structured ExtractedBook (pages, outline, running headers)."""
        is_bytes = isinstance(source, (bytes, bytearray))
        ext = os.path.splitext(filename if is_bytes else str(source))[1].lower() if (filename or not is_bytes) else ""
        if is_bytes:
            if ext == ".pdf" or source.startswith(b"%PDF"):
                try:
                    from backend.book_extract import extract_pdf
                except ImportError:
                    from book_extract import extract_pdf
                return extract_pdf(source)
            text = source.decode("utf-8", errors="replace")
            try:
                from backend.book_extract import PageText, ExtractedBook
            except ImportError:
                from book_extract import PageText, ExtractedBook
            return ExtractedBook(pages=[PageText(page_index=1, text=text)])

        if not os.path.exists(source):
            raise FileNotFoundError(f"File not found: {source}")
        if ext == ".pdf":
            try:
                from backend.book_extract import extract_pdf
            except ImportError:
                from book_extract import extract_pdf
            return extract_pdf(source)
        with open(source, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        try:
            from backend.book_extract import PageText, ExtractedBook
        except ImportError:
            from book_extract import PageText, ExtractedBook
        return ExtractedBook(pages=[PageText(page_index=1, text=text)])

    @staticmethod
    def extract_text_from_file(file_path: str) -> str:
        """Extracts text from a given file path on disk (PDF, EPUB, MOBI, TXT, MD)."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".pdf":
            try:
                try:
                    from backend.book_extract import extract_pdf
                except ImportError:
                    from book_extract import extract_pdf
                book = extract_pdf(file_path)
                return book.text
            except Exception as e:
                print(f"[MaterialParser] extract_pdf error: {e}. Falling back to byte extractor.")
                with open(file_path, "rb") as f:
                    return MaterialParser.extract_text_from_document_bytes(f.read(), filename=file_path)
        elif ext in [".epub", ".mobi", ".xps", ".fb2"]:
            with open(file_path, "rb") as f:
                return MaterialParser.extract_text_from_document_bytes(f.read(), filename=file_path)
        else:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                return f.read()

    @staticmethod
    def clean_text(raw_text: str) -> str:
        """Sanitizes text by stripping header/footer noise, page artifacts, and irregular whitespace."""
        text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
        # Remove repeated page markers
        text = re.sub(r"--- Page \d+ ---", "", text)
        # Normalize multiple blank lines to double newline
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Remove non-printable control characters except standard whitespace
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        return text.strip()

    # Regex patterns for non-theory sections (Appendix, Bibliography, Solutions, Front-matter)
    NON_THEORY_SECTION_PATTERN = re.compile(
        r"^(?:Appendix(?:\s+[A-Z0-9]+)?|Appendices|Bibliography|References|Works\s+Cited|Glossary|Index(?:\s+of\s+Terms)?|Solutions\s+(?:to|for)|Answers\s+to|Table\s+of\s+Contents|TOC|Preface|Foreword|Dedication|Acknowledgements|Copyright|Publisher|About\s+the\s+Authors?|Creative\s+Commons|OpenStax|License|All\s+Rights\s+Reserved|ISBN)\b",
        re.IGNORECASE
    )

    BOILERPLATE_SUBSTRINGS = (
        "licensed under",
        "creative commons",
        "all rights reserved",
        "isbn",
        "cataloging-in-publication",
        "library of congress",
        "openstax",
        "open textbook",
        "printed in",
        "is designed to",
        "provides a comprehensive",
        "prepares students",
        "we will explore",
        "in this chapter we"
    )

    @classmethod
    def detect_subject(cls, title: str, text: str, fallback: str = "General") -> str:
        """
        Intelligently identifies the academic domain of a document based on title and content semantics.
        Eliminates incorrect default tagging (e.g. tagging Computer Science books as Physics).
        """
        combined = f"{title}\n{text[:20000]}".lower()

        scores = {
            "Computer Science": sum(combined.count(w) for w in [
                "computer science", "software", "algorithm", "programming", "data structure",
                "computational", "database", "python", "code", "network", "cybersecurity",
                "operating system", "cloud", "compiler", "binary", "hardware", "machine learning",
                "api", "web application", "turing machine", "big o", "object-oriented", "data management"
            ]),
            "Physics": sum(combined.count(w) for w in [
                "physics", "velocity", "acceleration", "force", "thermodynamics", "momentum",
                "gravity", "quantum", "kinetic", "electromagnetism", "optics", "newton", "wave",
                "energy", "friction", "relativity", "electric current", "magnetic field"
            ]),
            "Mathematics": sum(combined.count(w) for w in [
                "calculus", "derivative", "integral", "algebra", "matrix", "matrices", "geometry",
                "probability", "vector space", "differential equation", "polynomial", "theorem",
                "topology", "eigenvalue", "proof"
            ]),
            "Biology": sum(combined.count(w) for w in [
                "biology", "cell", "organism", "dna", "rna", "genetics", "evolution", "ecology",
                "protein", "species", "photosynthesis", "membrane", "enzyme", "tissue", "metabolism"
            ]),
            "Chemistry": sum(combined.count(w) for w in [
                "chemistry", "molecule", "reaction", "stoichiometry", "acid", "base", "periodic table",
                "chemical bond", "orbital", "organic chemistry", "enthalpy", "catalyst"
            ]),
            "Engineering": sum(combined.count(w) for w in [
                "engineering", "circuit", "stress", "strain", "fluid mechanics", "structural",
                "control system", "signal processing", "robotics", "cad"
            ])
        }

        # Check title override first
        title_lower = title.lower()
        if any(w in title_lower for w in ["computer", "software", "algorithm", "data science", "cs"]):
            return "Computer Science"
        if any(w in title_lower for w in ["physic", "mechanics", "thermo"]):
            return "Physics"
        if any(w in title_lower for w in ["math", "calculus", "algebra", "stat"]):
            return "Mathematics"
        if any(w in title_lower for w in ["bio", "genetics", "organism"]):
            return "Biology"
        if any(w in title_lower for w in ["chem", "organic"]):
            return "Chemistry"

        best_subject, best_score = max(scores.items(), key=lambda x: x[1])
        if best_score >= 4:
            return best_subject

        return fallback if fallback and fallback != "General" else "Computer Science"

    @classmethod
    def strip_front_matter_and_toc(cls, text: str) -> str:
        """
        Detects and discards textbook front-matter: prefaces, publisher info, copyright,
        reviewer lists, and Table of Contents (TOC) before Chapter 1 begins.
        """
        early_slice = text[:35000]
        has_front_matter = bool(re.search(
            r"\b(?:OpenStax|Senior Contributing Author|Preface|About\s+the\s+Authors?|Reviewers|Contents|Table\s+of\s+Contents|To\s+learn\s+more\s+about\s+OpenStax)\b",
            early_slice,
            re.IGNORECASE
        ))

        if not has_front_matter:
            return text

        # Find where Chapter 1 / Section 1.1 truly begins in the body text
        # If a Table of Contents is present, the actual Chapter 1 appears after the Preface/TOC
        tocs = [m.start() for m in re.finditer(r"\b(?:Table\s+of\s+Contents|CONTENTS)\b", early_slice, re.IGNORECASE)]
        prefaces = [m.start() for m in re.finditer(r"\bPreface\b", early_slice, re.IGNORECASE)]
        min_start_pos = 0
        if prefaces:
            min_start_pos = max(prefaces) + 200
        elif tocs:
            min_start_pos = max(tocs) + 1500

        body_candidates = [
            m for m in re.finditer(r"(?:^|\n)\s*(?:###\s*1\.1\b|Chapter\s+1\b|CHAPTER\s+1\b|1\.1\s+[A-Z][a-zA-Z]|1\s*[\u2022\u25cf\u25cb\u25aa\u25ab\ufffd\*\-]\s*[A-Z][a-zA-Z]|Unit\s+1\b|Part\s+1\b)", early_slice)
            if m.start() >= min_start_pos
        ]

        if body_candidates:
            return text[body_candidates[0].start():].strip()

        any_ch1 = re.search(r"(?:^|\n)\s*(?:###\s*1\.1\b|Chapter\s+1\b|CHAPTER\s+1\b|1\.1\s+[A-Z][a-zA-Z])", early_slice)
        if any_ch1 and any_ch1.start() > 2000:
            return text[any_ch1.start():].strip()

        return text

    @classmethod
    def is_non_theory_section(cls, title: str) -> bool:
        """Determines whether a detected section heading is an appendix, front-matter, or index clutter."""
        clean_title = title.strip().lstrip("#").strip()
        if cls.NON_THEORY_SECTION_PATTERN.search(clean_title):
            return True
        low = clean_title.lower()
        return any(b in low for b in cls.BOILERPLATE_SUBSTRINGS)

    @classmethod
    def is_valid_heading(cls, title: str) -> bool:
        """Validates that a string is a genuine instructional heading rather than an explanatory sentence."""
        t = title.strip().lstrip("#").strip()
        if len(t) < 3 or len(t) > 95:
            return False
        # Must contain at least one alphabetic word of length >= 3
        if not re.search(r"[a-zA-Z]{3,}", t):
            return False
        if cls.is_non_theory_section(t):
            return False
        words = t.split()
        if len(words) > 13:
            return False
        if t.endswith(".") and len(words) > 5:
            return False
        return True

    @staticmethod
    def detect_outline_or_chapters(text: str, max_chapters: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Attempts to detect logical chapters/sections in text using headings or regex patterns.
        Filters out Table of Contents (TOC) listings, Front-Matter (Preface), and Back-Matter (Appendixes, Solutions, Index, Bibliography)
        to isolate 100% pure, substantive core instructional theory without mixing chapters.
        Deduplicates recurring running page headers and consolidates micro-sections into coherent study chapters.
        """
        cleaned = MaterialParser.clean_text(text)
        cleaned = MaterialParser.strip_front_matter_and_toc(cleaned)

        # 1. First Priority: Check for Major Numbered Chapters with Subsections (e.g. 1.1, 1.2, 2.1, ..., 10.1, 15.3)
        sec_pattern = re.compile(r'(?:^|\n)[ \t]*#{0,4}[ \t]*([1-9]\d*)\.([0-9]+)[ \t]+([A-Z][^\n]{3,80})')
        sec_matches = list(sec_pattern.finditer(cleaned))
        ch_numbers = set(int(m.group(1)) for m in sec_matches)

        if len(sec_matches) >= 3 and len(ch_numbers) >= 2:
            grouped_chapters: Dict[int, Dict[str, Any]] = {}
            for m in sec_matches:
                ch_idx = int(m.group(1))
                sec_idx = int(m.group(2))
                raw_title = m.group(3).strip()
                if raw_title.lower().endswith("license)") or "table" in raw_title.lower():
                    continue
                if ch_idx not in grouped_chapters:
                    grouped_chapters[ch_idx] = {
                        "main_title": raw_title,
                        "sections": []
                    }
                grouped_chapters[ch_idx]["sections"].append({
                    "sec_idx": sec_idx,
                    "title": raw_title,
                    "pos": m.start()
                })

            # Deduplicate sections by sec_idx for each chapter
            for ch_idx in grouped_chapters:
                seen_sec = set()
                deduped_secs = []
                for s in grouped_chapters[ch_idx]["sections"]:
                    if s["sec_idx"] not in seen_sec:
                        seen_sec.add(s["sec_idx"])
                        deduped_secs.append(s)
                grouped_chapters[ch_idx]["sections"] = deduped_secs

            sorted_chs = sorted(grouped_chapters.keys())
            major_theory_chapters: List[Dict[str, Any]] = []
            for i, ch_num in enumerate(sorted_chs):
                first_pos = grouped_chapters[ch_num]["sections"][0]["pos"]
                next_pos = grouped_chapters[sorted_chs[i + 1]]["sections"][0]["pos"] if i + 1 < len(sorted_chs) else len(cleaned)
                ch_text = cleaned[first_pos:next_pos].strip()

                # Strip trailing chapter review questions/exercises to keep instructional theory pure
                review_m = re.search(r'(?:^|\n)\s*(?:\d+\s*[\u2022\u25cf\u25cb\u25aa\u25ab\ufffd\*\-]\s*Chapter\s+Review|Chapter\s+Review|Exercises|Review\s+Questions)\b', ch_text)
                if review_m:
                    ch_text = ch_text[:review_m.start()].strip()

                # Try to find the actual parent chapter heading appearing just before
                # the first subsection block, or from the chapter's title page/intro
                pre_text = cleaned[max(0, first_pos - 1200):first_pos]
                parent_heading_m = re.search(r'(?:^|\n)[ \t]*#{1,2}[ \t]+([A-Z][^\n]{3,80})\s*$', pre_text)
                ch_explicit_m = re.search(r'(?im)^[ \t]*Chapter\s+' + str(ch_num) + r'\b[:\s\-–—]+([A-Z][^\n]{3,80})\s*$', cleaned[:next_pos])
                bare_outline_m = re.search(r'(?im)^[ \t]*' + str(ch_num) + r'[ \t]*\n[ \t]*([A-Z][^\n]{3,80})\s*\n(?:[^\n]*\n)*?[ \t]*chapter\s+outline\b', cleaned[:next_pos])
                inverted_num_m = re.search(r'(?im)^[ \t]*([A-Z][A-Za-z\s]{3,80})\s*\n[ \t]*' + str(ch_num) + r'\s*$', cleaned[:next_pos])

                if parent_heading_m:
                    main_title = parent_heading_m.group(1).strip()
                elif ch_explicit_m:
                    main_title = ch_explicit_m.group(1).strip()
                elif bare_outline_m:
                    main_title = bare_outline_m.group(1).strip()
                elif inverted_num_m and inverted_num_m.group(1).strip().lower() not in ("contents", "table of contents", "preface"):
                    main_title = inverted_num_m.group(1).strip()
                else:
                    main_title = grouped_chapters[ch_num]["main_title"]

                clean_ch_title = f"Chapter {ch_num}: {main_title}"
                if len(ch_text) >= 800:
                    unique_subs = []
                    seen_labels = set()
                    for s in grouped_chapters[ch_num]["sections"]:
                        lbl = f"{ch_num}.{s['sec_idx']}"
                        if lbl not in seen_labels:
                            seen_labels.add(lbl)
                            unique_subs.append({"sec_idx": lbl, "title": s["title"]})

                    major_theory_chapters.append({
                        "chapter_index": len(major_theory_chapters) + 1,
                        "title": clean_ch_title,
                        "content": ch_text,
                        "subsections": unique_subs
                    })

            if major_theory_chapters:
                return major_theory_chapters[:max_chapters] if max_chapters else major_theory_chapters
        
        # 2. Pattern for Standard Textbook chapters, Markdown headers, Parts, Lectures
        pattern = re.compile(
            r"(?:^|\n)\s*(#{1,3}\s+|Chapter\s+(?:\d+|[I|V|X]+)[:\s\-\.]*|Unit\s+(?:\d+|[I|V|X]+)[:\s\-\.]*|"
            r"Module\s+(?:\d+|[I|V|X]+)[:\s\-\.]*|Part\s+(?:\d+|[I|V|X]+)[:\s\-\.]*|Lesson\s+\d+[:\s\-\.]*|"
            r"Lecture\s+\d+[:\s\-\.]*|Topic\s+\d+[:\s\-\.]*|Section\s+\d+[:\s\-\.]*|[0-9]+\.[0-9]*\s+|"
            r"[I|V|X]+\.\s+|(?:Introduction|Methodology|Overview|Foundations)(?:[:\s\-\.]*))([^\n]{0,80})(?:\n|$)",
            re.IGNORECASE
        )
        
        matches = list(pattern.finditer(cleaned))
        raw_sections: List[Dict[str, Any]] = []
        
        if len(matches) >= 2:
            candidates: List[Dict[str, Any]] = []
            for i, match in enumerate(matches):
                title_prefix = match.group(1).strip()
                title_text = match.group(2).strip()
                full_title = f"{title_prefix} {title_text}".strip().lstrip("#").strip()
                
                # Sanitize title: strip bullets, unicode artifacts, trailing dotted leaders and page numbers
                full_title = re.sub(r"[\u2022\u25cf\u25cb\u25aa\u25ab\ufffd\*\t]+", " ", full_title)
                full_title = re.sub(r"\.{2,}\s*\d*", "", full_title)
                full_title = re.sub(r"\s+\d{1,4}$", "", full_title)
                full_title = re.sub(r"\s{2,}", " ", full_title).strip()
                
                if not MaterialParser.is_valid_heading(full_title):
                    continue
                
                start_pos = match.end()
                end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(cleaned)
                content = cleaned[start_pos:end_pos].strip()
                
                # Deduplicate repeated running page headers (e.g. '1.1 Computer Science' on every page)
                norm_curr = re.sub(r"[^a-z0-9]", "", full_title.lower())
                if candidates:
                    norm_prev = re.sub(r"[^a-z0-9]", "", candidates[-1]["title"].lower())
                    if norm_curr == norm_prev or (len(norm_curr) >= 8 and (norm_curr in norm_prev or norm_prev in norm_curr)):
                        candidates[-1]["content"] += f"\n\n{content}"
                        candidates[-1]["content_len"] = len(candidates[-1]["content"])
                        continue

                candidates.append({
                    "title": full_title,
                    "content": content,
                    "content_len": len(content),
                    "pos": match.start()
                })
                
            # Filter TOC: identify if early matches are compact TOC entries
            first_substantive_idx = 0
            for idx, c in enumerate(candidates):
                if c["content_len"] >= 600 and not MaterialParser.is_non_theory_section(c["title"]):
                    first_substantive_idx = idx
                    break
            
            valid_candidates = candidates[first_substantive_idx:] if first_substantive_idx > 0 else candidates

            for c in valid_candidates:
                content = c["content"]
                full_title = c["title"]
                
                is_toc_snippet = (
                    len(content) < 400 and (
                        bool(re.search(r"\b(?:Key Terms|Group Project|Chapter Review|Quantitative Problems|Problems|Exercises)\s+\d+", content))
                        or bool(re.search(r"\.{2,}\s*\d+", content))
                        or bool(re.search(r"\b\d+\s+\b\d+\s+\b\d+", content))
                    )
                )
                
                if is_toc_snippet:
                    continue
                
                # Only accept sections with substantive instructional body text (at least 200 characters)
                if len(content) >= 200:
                    raw_sections.append({
                        "title": full_title,
                        "content": content
                    })
                elif raw_sections and content:
                    # Consolidate brief sub-section into preceding section so no text is lost
                    raw_sections[-1]["content"] += f"\n\n### {full_title}\n{content}"
                    
        # Filter out non-theory sections (Appendixes, Front-matter, Bibliographies, Solution Keys)
        theory_chapters: List[Dict[str, Any]] = []
        for s in raw_sections:
            if MaterialParser.is_non_theory_section(s["title"]):
                continue
            
            # Fragment consolidation: Merge sub-headings (e.g. 'Section 1.1', '1.1', '### Subtopic')
            # or sub-fragments into parent chapter.
            is_sub_heading = bool(re.match(r"^(?:Section\s+\d+\.\d+|Subsection|###|\d+\.\d+)", s["title"], re.IGNORECASE))
            if theory_chapters and is_sub_heading:
                prev = theory_chapters[-1]
                prev["content"] = prev["content"] + "\n\n" + f"### {s['title']}\n" + s["content"]
                continue

            if max_chapters and len(theory_chapters) >= max_chapters:
                # Merge into the final chapter rather than creating excessive micro-chapters
                theory_chapters[-1]["content"] += "\n\n" + f"### {s['title']}\n" + s["content"]
                continue

            theory_chapters.append({
                "chapter_index": len(theory_chapters) + 1,
                "title": s["title"],
                "content": s["content"]
            })
                    
        # If no explicit chapter structure detected or all were filtered (e.g. continuous narrative or dense essay),
        # slice the substantive body into cognitively optimal, rich study sections
        if not theory_chapters:
            # Discard initial TOC pages if detected
            substantive_text = cleaned
            toc_match = re.search(r"(?:Table\s+of\s+Contents|Contents)\b.*?(?=Chapter\s+1\b|Unit\s+1\b|1\.\s+Introduction\b|Introduction\b)", cleaned, re.DOTALL | re.IGNORECASE)
            if toc_match:
                substantive_text = cleaned[toc_match.end():].strip()

            paragraphs = [p.strip() for p in substantive_text.split("\n\n") if len(p.strip()) > 80]
            if not paragraphs:
                paragraphs = [p.strip() for p in cleaned.split("\n\n") if len(p.strip()) > 30]
            if not paragraphs:
                paragraphs = [cleaned]
                
            # Cognitively optimal section sizing: approximately 3,000 - 5,000 characters per section
            current_section_paras: List[str] = []
            current_len = 0
            slice_idx = 1

            for p in paragraphs:
                current_section_paras.append(p)
                current_len += len(p)

                # Split when reaching cognitive section size (~5,000 chars — richer, more substantive chunks)
                if current_len >= 5000:
                    section_text = "\n\n".join(current_section_paras)
                    # Derive title from the first sentence that looks like a complete thought (not just a symbol line)
                    candidate_lines = [l.strip() for l in section_text.split("\n") if len(l.strip()) > 15 and not re.match(r'^[#\*\d\.\-:=\s]+$', l)]
                    first_meaningful = candidate_lines[0][:80] if candidate_lines else ""
                    first_meaningful = re.sub(r'^[#\*\d\.\-:]+\s*', '', first_meaningful).strip()
                    title = f"Section {slice_idx}: {first_meaningful}" if len(first_meaningful) > 10 else f"Section {slice_idx}: Theoretical Foundations"
                    
                    theory_chapters.append({
                        "chapter_index": slice_idx,
                        "title": title,
                        "content": section_text
                    })
                    current_section_paras = []
                    current_len = 0
                    slice_idx += 1
                    if max_chapters and slice_idx > max_chapters:
                        break

            # Flush remaining paragraphs
            if current_section_paras:
                section_text = "\n\n".join(current_section_paras)
                if len(section_text) >= 200:
                    if theory_chapters and len(section_text) < 1000:
                        # Append to last chapter to avoid a tiny trailing stub
                        theory_chapters[-1]["content"] += "\n\n" + section_text
                    else:
                        first_line = section_text.split("\n")[0][:70].strip()
                        first_line = re.sub(r"[#\*\d\.\-:]+", " ", first_line).strip()
                        title = f"Section {slice_idx}: {first_line}" if len(first_line) > 10 else f"Section {slice_idx}: Advanced Synthesis"
                        theory_chapters.append({
                            "chapter_index": slice_idx,
                            "title": title,
                            "content": section_text
                        })

        return theory_chapters

    @staticmethod
    def create_semantic_chunks(text: str, chunk_size: int = 400, overlap: int = 50) -> List[str]:
        """Creates semantic sentence/paragraph chunks with true sliding overlap for ChromaDB vector embeddings."""
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if len(s.strip()) > 0]
        if not sentences:
            paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 30]
            sentences = paragraphs if paragraphs else [text.strip()]
        
        chunks: List[str] = []
        current_chunk: List[str] = []
        current_words = 0
        
        for s in sentences:
            words = len(s.split())
            if current_words + words > chunk_size and current_chunk:
                chunks.append(" ".join(current_chunk))
                # Compute sliding overlap
                overlap_words = 0
                overlap_chunk: List[str] = []
                for prev_s in reversed(current_chunk):
                    prev_len = len(prev_s.split())
                    if overlap_words + prev_len <= overlap:
                        overlap_chunk.insert(0, prev_s)
                        overlap_words += prev_len
                    else:
                        break
                current_chunk = overlap_chunk
                current_words = overlap_words
                
            current_chunk.append(s)
            current_words += words
            
        if current_chunk:
            chunks.append(" ".join(current_chunk))
            
        return chunks if chunks else [text[:1000]]
