"""
Unit and integration tests for theory quality enhancement, Gemini output normalizer,
and BookStructurer printed TOC and section extraction fixes.
"""

import os
import sys
import pytest

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from question_generator import normalize_ai_content, QuestionGeneratorEngine
from book_structurer import BookStructurer


def test_normalize_ai_content_various_shapes():
    """Verifies that normalize_ai_content converts flat strings, lists of dicts, and empty values into clean strings."""
    assert normalize_ai_content("Hello World") == "Hello World"
    assert normalize_ai_content([{"text": "Part 1 "}, {"text": "Part 2"}]) == "Part 1 Part 2"
    assert normalize_ai_content(["Direct ", "String ", "List"]) == "Direct String List"
    assert normalize_ai_content(None) == ""
    assert normalize_ai_content("") == ""
    assert normalize_ai_content([]) == ""


def test_book_structurer_printed_toc_bare_numbered_chapters():
    """Verifies that printed TOCs formatted like '2 Equations and Inequalities 81' are parsed cleanly."""
    text = (
        "Table of Contents\n\n"
        "1 Prerequisites 1\n"
        "1.1 Real Numbers 1\n"
        "1.2 Exponents 15\n"
        "2 Equations and Inequalities 40\n"
        "2.1 Rectangular Coordinates 40\n"
        "2.2 Linear Equations 55\n"
        "2.3 Quadratic Equations 70\n"
        "3 Functions 90\n"
        "3.1 Function Notation 90\n"
        "3.2 Domain and Range 105\n\n"
        + "Chapter 1: Prerequisites\n\n1.1 Real Numbers\n"
        + "Instructional content on algebra essentials. " * 80
        + "\n\n1.2 Exponents\n"
        + "Instructional content on rules of exponents. " * 80
        + "\n\nChapter 2: Equations and Inequalities\n\n2.1 Rectangular Coordinates\n"
        + "Instructional content on Cartesian plane and coordinates. " * 80
        + "\n\n2.2 Linear Equations\n"
        + "Instructional content on solving linear equations. " * 80
        + "\n\n2.3 Quadratic Equations\n"
        + "Instructional content on the quadratic formula. " * 80
        + "\n\nChapter 3: Functions\n\n3.1 Function Notation\n"
        + "Instructional content on inputs, outputs, and mappings. " * 80
        + "\n\n3.2 Domain and Range\n"
        + "Instructional content on allowed domains. " * 80
    )
    structurer = BookStructurer(text)
    plan = structurer.plan()

    assert plan.source in ("printed_toc", "inferred_headings")
    assert len(plan.parsed_chapters) >= 3
    ch2 = next(c for c in plan.parsed_chapters if c["chapter"] == 2)
    assert ch2["title"] == "Equations and Inequalities"
    assert len(ch2["sections"]) == 3
    assert ch2["sections"][0]["label"] == "2.1"
    assert ch2["sections"][0]["title"] == "Rectangular Coordinates"
    assert ch2["sections"][1]["label"] == "2.2"
    assert ch2["sections"][1]["title"] == "Linear Equations"


def test_book_structurer_section_scoring_with_running_headers():
    """Verifies that recurring page running headers do not inflate section counts and force chunking fallback."""
    # Create a chapter body with 3 genuine sections, but with 20 running headers repeated
    body = (
        "Chapter 2: Equations and Inequalities\n\n"
        "2.1 Rectangular Coordinates\n"
        "Core text of section 2.1.\n"
        "2.1 • Rectangular Coordinates 41\n"
        "More text.\n"
        "2.1 • Rectangular Coordinates 43\n"
        "More text.\n"
        "2.2 Linear Equations\n"
        "Core text of section 2.2.\n"
        "2.2 • Linear Equations 57\n"
        "More text.\n"
        "2.2 • Linear Equations 59\n"
        "2.3 Quadratic Equations\n"
        "Core text of section 2.3.\n"
        "2.3 • Quadratic Equations 71\n"
        "More text.\n"
    )
    text = (
        "Table of Contents\n1 Intro\n2 Middle\n3 End\n\n"
        + ("# Chapter 1\nIntro text " * 30)
        + "\n\n" + body
        + "\n\n" + ("# Chapter 3\nEnd text " * 30)
    )
    structurer = BookStructurer(text)
    plan = structurer.plan()
    plan.section_kind = "numdot"

    starts = structurer.section_starts(body, 2, plan)
    # Starts must have exactly 3 deduplicated sections (2.1, 2.2, 2.3)
    labels = [s[1] for s in starts]
    assert labels == ["2.1", "2.2", "2.3"]
    titles = [s[2] for s in starts]
    assert "Rectangular Coordinates" in titles[0]
    assert "Linear Equations" in titles[1]
    assert "Quadratic Equations" in titles[2]


def test_stem_domain_theory_generation_offline():
    """Verifies that offline theory generation for STEM domains returns rigorous formulations and principles."""
    engine = QuestionGeneratorEngine()

    calc_res = engine.generate_chapter_theory_and_cards(
        chapter_title="Derivatives and Rates of Change",
        chapter_text="Minimal introductory text without prose definitions.",
        subject="Calculus",
        use_llm=False,
    )
    assert any("Derivative" in f["title"] or "lim" in f["formula"] for f in calc_res["deep_theory"]["formulations"])
    assert any("Rate" in p["title"] or "Continuity" in p["title"] for p in calc_res["deep_theory"]["principles"])

    phys_res = engine.generate_chapter_theory_and_cards(
        chapter_title="Newtonian Mechanics",
        chapter_text="Minimal introductory text without prose definitions.",
        subject="Physics",
        use_llm=False,
    )
    assert any("Newton" in f["title"] or "Work" in f["title"] for f in phys_res["deep_theory"]["formulations"])
    assert any("Conservation" in p["title"] or "Forces" in p["title"] for p in phys_res["deep_theory"]["principles"])


def test_worked_examples_schema_and_solution_retention():
    """Verifies that _extract_worked_examples retains the Solution block and provides title and content."""
    text = (
        "Introductory prose.\n\n"
        "EXAMPLE 1\n\n"
        "Solving a Linear Equation\n"
        "Solve 2x + 4 = 10 for x.\n\n"
        "Solution\n"
        "Subtract 4 from both sides to obtain 2x = 6. Then divide by 2 to find x = 3.\n\n"
        "Check Your Understanding\n"
        "Try solving 3x - 1 = 8.\n"
    )
    examples = QuestionGeneratorEngine._extract_worked_examples(text)
    assert len(examples) >= 1
    ex = examples[0]
    assert "title" in ex and "content" in ex
    assert "EXAMPLE 1" in ex["title"]
    assert "Solving a Linear Equation" in ex["content"]
    assert "Solution" in ex["content"]
    assert "x = 3" in ex["content"]
    # Schema compatibility
    assert "source" in ex and "worked_problem" in ex
    assert ex["content"] == ex["worked_problem"]


def test_ground_deep_theory_preserves_domain_formulations_against_trivial_scraps():
    """Verifies that trivial regex matches (x = 0) do not wipe out rich domain formulations in deep_theory."""
    engine = QuestionGeneratorEngine()
    text = "We note that x = 0 is a boundary point. A student Caroline planned a trip."
    res = engine.generate_chapter_theory_and_cards(
        chapter_title="Equations and Inequalities",
        chapter_text=text,
        subject="Mathematics",
        use_llm=False,
    )
    formula_titles = [f["title"] for f in res["deep_theory"]["formulations"]]
    assert any("Quadratic" in t for t in formula_titles)
    assert any("Slope" in t for t in formula_titles)
    # The student name 'Caroline' must never leak into principles
    assert not any("Caroline" in p.get("title", "") for p in res["deep_theory"]["principles"])
