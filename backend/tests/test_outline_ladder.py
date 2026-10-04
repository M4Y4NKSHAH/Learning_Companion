"""
================================================================================
 Learning Companion — Test Suite: Outline Ladder & Structure Inference
================================================================================
"""

import json
import os
import sys
import pytest

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from book_extract import extract_pdf, ExtractedBook, PageText, OutlineEntry
from book_structurer import BookStructurer
from divide_book import SmartBookDivider

CS_PDF_PATH = r"C:\Users\pc\Downloads\COMPUTER_SCIENCE-compressed.pdf"
PHYSICS_TXT_PATH = os.path.join(backend_dir, "data", "curriculum", "physics_textbook.txt")
GOLDEN_PATH = os.path.join(backend_dir, "tests", "fixtures", "cs_book_golden.json")


def test_rung1_embedded_outline_cs_book():
    """Asserts that on COMPUTER_SCIENCE-compressed.pdf, Rung 1 extracts 14 chapters
    and 61 sections matching backend/tests/fixtures/cs_book_golden.json."""
    assert os.path.exists(CS_PDF_PATH), f"Target test book not found at {CS_PDF_PATH}"
    assert os.path.exists(GOLDEN_PATH), f"Golden fixture not found at {GOLDEN_PATH}"

    with open(GOLDEN_PATH, "r", encoding="utf-8") as f:
        golden = json.load(f)

    extracted_book = extract_pdf(CS_PDF_PATH)
    assert len(extracted_book.pages) == golden["pdf_pages"]
    assert len(extracted_book.outline) > 0
    assert len(extracted_book.running_headers) >= 5

    structurer = BookStructurer(extracted_book=extracted_book)
    plan = structurer.plan()

    assert plan.source == "embedded_outline"
    assert len(plan.parsed_chapters) == golden["expected_chapters"]

    total_sections = sum(len(ch["sections"]) for ch in plan.parsed_chapters)
    assert total_sections == golden["expected_sections"]

    # Verify each chapter and section against golden fixture
    for ch_idx, (g_ch, e_ch) in enumerate(zip(golden["chapters"], plan.parsed_chapters)):
        assert e_ch["chapter"] == g_ch["chapter"]
        assert e_ch["title"] == g_ch["title"]
        assert e_ch["pdf_page_start"] == g_ch["pdf_page_start"]
        assert e_ch["chapter_review_pdf_page"] == g_ch["chapter_review_pdf_page"]

        assert len(e_ch["sections"]) == len(g_ch["sections"])
        for s_idx, (g_sec, e_sec) in enumerate(zip(g_ch["sections"], e_ch["sections"])):
            assert e_sec["label"] == g_sec["label"]
            assert e_sec["title"] == g_sec["title"]
            assert e_sec["pdf_page_start"] == g_sec["pdf_page_start"]

            # Check approximate word counts with 15% tolerance as specified in golden fixture note
            if "approx_words" in g_sec and "approx_words" in e_sec:
                expected_w = g_sec["approx_words"]
                actual_w = e_sec["approx_words"]
                diff_pct = abs(actual_w - expected_w) / expected_w
                assert diff_pct < 0.15, (
                    f"Section {e_sec['label']} words diff too high: {actual_w} vs {expected_w} ({diff_pct:.1%})"
                )


def test_regression_physics_textbook_34_chapters():
    """Asserts regression test on backend/data/curriculum/physics_textbook.txt
    still produces 34 chapters without regression."""
    assert os.path.exists(PHYSICS_TXT_PATH), f"Physics textbook not found at {PHYSICS_TXT_PATH}"

    with open(PHYSICS_TXT_PATH, "r", encoding="utf-8") as f:
        text = f.read()

    # 1. Direct structurer plan check
    structurer = BookStructurer(text)
    plan = structurer.plan()
    assert plan.source in ("printed_toc", "inferred_headings")
    assert len(plan.chapter_matches) == 34

    # 2. SmartBookDivider full division check
    divider = SmartBookDivider(book_key="physics")
    toc = divider.parse_toc()
    assert len(toc) == 34
    bodies = divider._locate_chapter_bodies()
    assert len(bodies) == 34


def test_cpp_include_not_misclassified_as_h1_chapters():
    """Verifies that C++ preprocessor directives (#include, #define, #pragma)
    are never misclassified as markdown H1 chapters."""
    prose = "Programming languages allow developers to communicate instructions to computers efficiently. " * 3
    cpp_in_book = f"""
1. Introduction to Programming
This chapter introduces basics of C++ programming.
{prose}
#include <iostream>
#include <vector>
#include <string>

2. Standard Input and Output
Reading and writing from console streams and files.
{prose}
#include <stdio.h>
#include <stdlib.h>
#pragma omp parallel num_threads(4)

3. Advanced Data Structures
Templates and standard template library algorithms.
{prose}
#include <map>
#include <set>
"""
    structurer = BookStructurer(cpp_in_book)
    plan = structurer.plan()
    assert plan.chapter_kind != "hash_headings"
    assert plan.chapter_kind in ("numbered_dot", "bare_num_title")
    for spot in plan.chapter_matches:
        assert "include <" not in spot.title
        assert "pragma" not in spot.title


def test_ladder_fallthrough_to_balanced_chunks():
    """Verifies that plain text with no headings falls through to Rung 4 balanced_chunks."""
    paragraph = "This is a continuous flow of narrative text without any headings or chapter numbers. " * 30
    prose = "\n\n".join(paragraph for _ in range(30))
    structurer = BookStructurer(prose)
    plan = structurer.plan()
    assert plan.source == "balanced_chunks"
    assert len(plan.chapter_matches) >= 2
    assert plan.chapter_kind == "none"


def test_part_level_embedded_outline_hierarchy():
    """Verifies that an outline with Level 1 Parts and Level 2 Chapters correctly
    detects chapters at Level 2 and records Level 1 entries as Units."""
    outline = [
        OutlineEntry(level=1, title="Part 1: Foundations of Computing", page=1),
        OutlineEntry(level=2, title="Chapter 1: Basics of Architecture", page=1),
        OutlineEntry(level=2, title="Chapter 2: Logic and Gates", page=20),
        OutlineEntry(level=2, title="Chapter 3: Memory Systems", page=40),
        OutlineEntry(level=1, title="Part 2: Software Engineering", page=60),
        OutlineEntry(level=2, title="Chapter 4: Algorithms and Control", page=60),
        OutlineEntry(level=2, title="Chapter 5: Object-Oriented Design", page=80),
    ]
    prose = "Textbook chapter material content for testing outline ladder. " * 50
    st = BookStructurer(text=prose, outline=outline)
    plan = st.plan()

    assert plan.source == "embedded_outline"
    assert len(plan.parsed_chapters) == 5
    assert [c["chapter"] for c in plan.parsed_chapters] == [1, 2, 3, 4, 5]
    assert plan.units is not None
    assert len(plan.units) == 2
    assert plan.units[0]["chapters"] == [1, 2, 3]
    assert plan.units[1]["chapters"] == [4, 5]


def test_bare_num_title_with_chapter_outline_marker():
    """Verifies that bare chapter number lines followed by title and Chapter Outline marker
    are correctly identified with exact titles and positions."""
    prose = "Body text exploring fundamental concepts in system design. " * 40
    book_text = f"""
1
Introduction to Computing
Chapter Outline
1.1 Computing Systems
{prose}
1.2 Information Representation
{prose}

2
Algorithms and Problem Solving
Chapter Outline
2.1 Problem Decomposition
{prose}
2.2 Sorting and Searching
{prose}

3
Data Structures
Chapter Outline
3.1 Linear Structures
{prose}
3.2 Tree Hierarchies
{prose}
"""
    st = BookStructurer(text=book_text)
    plan = st.plan()

    assert plan.source == "inferred_headings"
    assert len(plan.chapter_matches) == 3
    # Ensure titles are properly extracted without duplicating Chapter prefix
    titles = [s.title for s in plan.chapter_matches]
    assert "Introduction to Computing" in titles[0]
    assert "Algorithms and Problem Solving" in titles[1]
    assert "Data Structures" in titles[2]
    # Ensure first_pos starts at or before the chapter title/number, not inside section 1.1
    for spot in plan.chapter_matches:
        assert spot.pos < book_text.find("1.1 Computing Systems") or spot.number > 1


def test_non_monotonic_outline_falls_through():
    """Verifies that non-monotonic page numbers in embedded outline trigger fallthrough."""
    # Out of order: page 40 before page 10
    broken_outline = [
        OutlineEntry(level=1, title="Chapter 1: Basics", page=40),
        OutlineEntry(level=1, title="Chapter 2: Logic", page=10),
        OutlineEntry(level=1, title="Chapter 3: Memory", page=20),
    ]
    paragraph = "This is a body of text with standard numbered dot chapters.\n\n"
    book_text = (
        paragraph +
        "1. First Chapter\n" + ("Content text. " * 30) + "\n\n" +
        "2. Second Chapter\n" + ("Content text. " * 30) + "\n\n" +
        "3. Third Chapter\n" + ("Content text. " * 30) + "\n\n"
    )
    st = BookStructurer(text=book_text, outline=broken_outline)
    plan = st.plan()
    # Monotonicity failed -> must NOT be embedded_outline
    assert plan.source != "embedded_outline"
    assert plan.source in ("inferred_headings", "balanced_chunks")


def test_extract_pdf_bytes_interface():
    """Asserts that extract_pdf handles raw bytes directly as well as file paths."""
    assert os.path.exists(CS_PDF_PATH), f"Target test book not found at {CS_PDF_PATH}"
    with open(CS_PDF_PATH, "rb") as f:
        pdf_bytes = f.read()

    extracted = extract_pdf(pdf_bytes)
    assert isinstance(extracted, ExtractedBook)
    assert len(extracted.pages) > 0
    assert len(extracted.outline) > 0
    assert len(extracted.running_headers) > 0
    assert len(extracted.text) > 10000


def test_smart_divide_material_cs_book_14_chapters_and_deduped_subsections():
    """Asserts that _smart_divide_material with extracted_book ingests all 14 chapters
    with non-repeating titles and deduplicated subsections."""
    assert os.path.exists(CS_PDF_PATH), f"Target test book not found at {CS_PDF_PATH}"
    extracted_book = extract_pdf(CS_PDF_PATH)

    from app import _smart_divide_material
    chapters = _smart_divide_material(
        text=extracted_book.text,
        title="Computer Science",
        subject="Computer Science",
        academic_tier="Undergraduate",
        extracted_book=extracted_book,
        path=CS_PDF_PATH
    )

    assert len(chapters) == 14, f"Expected 14 chapters, got {len(chapters)}"

    # Ensure titles are distinct and match actual chapters, not all named 'Introduction to Computer Science'
    titles = [ch["title"] for ch in chapters]
    assert len(set(titles)) == 14, "Chapter titles should all be distinct"
    assert "Computer Science" in titles[0]
    assert "Computational Thinking" in titles[1]

    # Verify that subsections within every chapter are deduplicated
    for ch in chapters:
        subsections = ch.get("subsections", [])
        sec_labels = [s.get("label") or s.get("sec_idx") for s in subsections if s.get("label") or s.get("sec_idx")]
        assert len(sec_labels) == len(set(sec_labels)), f"Found duplicate subsections in chapter {ch['title']}: {sec_labels}"


def test_material_parser_detect_outline_deduplication_and_parent_title():
    """Asserts that detect_outline_or_chapters deduplicates recurring running page headers
    and extracts the true parent chapter title without overwriting with subsection 1.1."""
    from material_parser import MaterialParser

    prose = "Instructional computer science theory and architectural principles. " * 15
    text = f"""
    Chapter 1: Principles of Computation
    1.1 Computer Science Foundations
    {prose}
    1.1 Computer Science Foundations
    Running header content repeated.
    1.2 Algorithmic Thinking
    {prose}
    1.2 Algorithmic Thinking
    Running header content repeated.
    1.3 System Architectures
    {prose}

    Chapter 2: Computational Systems and Networks
    2.1 Network Protocols
    {prose}
    2.1 Network Protocols
    Running header.
    2.2 Distributed Systems
    {prose}
    """

    chapters = MaterialParser.detect_outline_or_chapters(text)
    assert len(chapters) >= 2

    ch1 = chapters[0]
    assert "Principles of Computation" in ch1["title"]
    # Check that subsections in ch1 are deduplicated (1.1, 1.2, 1.3 only once each)
    sec_indices = [s["sec_idx"] for s in ch1.get("subsections", [])]
    assert len(sec_indices) == len(set(sec_indices)), f"Subsections not deduplicated: {sec_indices}"
    assert "1.1" in sec_indices
    assert "1.2" in sec_indices


def test_prepare_chapter_context_multisection_sampling():
    """Asserts that QuestionGeneratorEngine._prepare_chapter_context extracts a balanced
    multi-section window (head 45%, mid 35%, tail 20%) with transition markers."""
    from question_generator import QuestionGeneratorEngine

    # 1. Short text returns clean text unchanged
    short = "This is a short chapter overview."
    assert QuestionGeneratorEngine._prepare_chapter_context(short, max_chars=7500) == short

    # 2. Long text (12,000 characters) is sampled with markers
    head_token = "ALPHA_FOUNDATION_TOKEN"
    mid_token = "BETA_CORE_ANALYSIS_TOKEN"
    tail_token = "GAMMA_APPLICATION_TOKEN"

    long_text = (
        (head_token + " " * 100) * 40 +
        "\n\n" +
        (mid_token + " " * 100) * 40 +
        "\n\n" +
        (tail_token + " " * 100) * 40
    )

    ctx = QuestionGeneratorEngine._prepare_chapter_context(long_text, max_chars=7500)
    assert "[... Core Section Analysis ...]" in ctx
    assert "[... Key Applications & Review ...]" in ctx
    assert head_token in ctx
    assert mid_token in ctx
    assert tail_token in ctx
    assert len(ctx) <= 7600


def test_material_parser_no_duplicate_chapter_prefix():
    """Asserts that markdown # Chapter 1: headings never result in duplicate 'Chapter 1: Chapter 1:'."""
    from material_parser import MaterialParser
    text = (
        "# Chapter 1: Introduction to Computer Science\n\n1.1 Foundations\n"
        + "Instructional text content for testing. " * 50
        + "\n1.2 Advanced\n"
        + "More content text here for testing. " * 50
        + "\n# Chapter 2: Algorithms\n\n2.1 Sorting\n"
        + "Algorithm content. " * 50
        + "\n2.2 Searching\n"
        + "Search content. " * 50
    )
    chs = MaterialParser.detect_outline_or_chapters(text)
    assert len(chs) == 2
    assert chs[0]["title"] == "Chapter 1: Introduction to Computer Science"
    assert chs[1]["title"] == "Chapter 2: Algorithms"


