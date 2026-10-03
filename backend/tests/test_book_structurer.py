"""
Structural-inference tests.

The book divider must work for *any* book a user supplies, not just OpenStax
PDF dumps, so these tests drive the inference layer with very different layouts:
numbered chapters, markdown notes, word numerals, unit/lesson books, bare
numbered chapters, front-matter TOCs, and books with no headings at all.
"""
import os
import sys

backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from book_structurer import (BookStructurer, roman_to_int,  # noqa: E402
                             slugify, word_to_int)
from divide_book import (SmartBookDivider, estimate_llm_build,  # noqa: E402
                         parse_chapter_selection, summarise_selection)

PROSE = ("Cells are the basic structural unit of every living organism. "
         "Their membranes regulate the exchange of matter and energy with the "
         "surrounding environment. Metabolism couples catabolic and anabolic "
         "reactions inside a single compartment. ")


def _prose(times: int = 6) -> str:
    return PROSE * times


def book_openstax() -> str:
    """TOC in the front matter, `CHAPTER N` headings, `N.M` sections."""
    toc = ["Contents", "CHAPTER 1", "Introduction 7"]
    for n in range(1, 5):
        toc += [f"CHAPTER {n}", f"Biology {n} 7"]
        toc += [f"{n}.{s} Topic number {s} {10 + s}" for s in range(1, 4)]
    out = "\n".join(toc) + "\n"
    for n in range(1, 5):
        out += f"\nCHAPTER {n}\nBiology {n}\n{_prose()}\n"
        for s in range(1, 4):
            out += f"\n{n}.{s} Topic number {s}\n{_prose(8)}\n"
        out += "\nGlossary\n" + _prose(2) + "\n"
    return out


def book_markdown() -> str:
    """A markdown note dump: `# Chapter n` plus `## n.s` sections."""
    out = "# My Notes on Systems\n\n"
    for n in range(1, 6):
        out += f"\n# Chapter {n}: Theme {n}\n\n{_prose(5)}\n"
        for s in range(1, 4):
            out += f"\n## {n}.{s} Sub theme {s}\n\n{_prose(7)}\n"
    return out


def book_word_numerals() -> str:
    """`Chapter One: Title` headings (word numerals) with an index page."""
    words = ["One", "Two", "Three", "Four"]
    out = "CONTENTS\n"
    for i, word in enumerate(words, 1):
        out += f"Chapter {word}: Subject {i} .......... {i * 20}\n"
    out += "\n"
    for i, word in enumerate(words, 1):
        out += f"\nChapter {word}: Subject {i}\n{_prose()}\n"
        for s in range(1, 4):
            out += f"\n{i}.{s} Detail {s}\n{_prose()}\n"
    return out


def book_units_lessons() -> str:
    """Two declared UNITs, each with four `Lesson n` chapters."""
    out = "Table of Contents\n"
    for u in range(1, 3):
        out += f"Unit {u} - Big Theme {u} .... {u * 30}\n"
        for lesson in range(1, 5):
            out += f"Lesson {lesson}: A topic {lesson} .... {u * 30 + lesson}\n"
    out += "\n"
    for u in range(1, 3):
        out += f"\nUNIT {u} - Big Theme {u}\n{_prose(3)}\n"
        for lesson in range(1, 5):
            out += f"\nLesson {lesson}: A topic {lesson}\n{_prose(5)}\n"
            for s in range(1, 3):
                out += f"\n{lesson}.{s} Sub idea {s}\n{_prose(4)}\n"
    return out


def book_numbered_dot() -> str:
    """Bare `1. Title` top-level headings, no chapter keyword."""
    out = ""
    for n in range(1, 6):
        out += f"\n{n}. Chapter topic {n}\n{_prose()}\n"
        for s in range(1, 4):
            out += f"\n{n}.{s} Section topic {s}\n{_prose()}\n"
    return out


def book_no_headings() -> str:
    """Long prose with no headings at all."""
    return _prose(220)


# --------------------------------------------------------------------------- #
# Session-scoped plans (inference is pure, so this keeps the suite fast)
# --------------------------------------------------------------------------- #
_CACHE = {}


def plan_for(name: str) -> object:
    if name not in _CACHE:
        _CACHE[name] = BookStructurer(globals()[name]()).plan()
    return _CACHE[name]


def test_openstax_layout_is_recognised():
    plan = plan_for("book_openstax")
    assert plan.chapter_kind == "chapter_digits"
    assert len(plan.chapter_matches) == 4          # TOC copies are not chapters
    assert plan.section_kind == "numdot"
    assert plan.body_start <= plan.chapter_matches[0].pos
    assert plan.confidence > 0.7


def test_markdown_notes_layout_is_recognised():
    plan = plan_for("book_markdown")
    assert plan.chapter_kind == "hash_headings"
    assert len(plan.chapter_matches) == 5          # the `# title` line is dropped
    assert plan.section_kind == "hash_headings"
    assert plan.section_level == 2
    assert "title" in " ".join(plan.notes)


def test_word_numeral_chapters_are_recognised():
    plan = plan_for("book_word_numerals")
    assert plan.chapter_kind == "chapter_word"
    assert len(plan.chapter_matches) == 4
    assert plan.section_kind == "numdot"


def test_unit_and_lesson_layout_is_recognised():
    plan = plan_for("book_units_lessons")
    assert plan.chapter_kind == "lesson_digits"
    assert len(plan.chapter_matches) == 8
    assert plan.units is not None and len(plan.units) == 2
    assert [len(u["chapters"]) for u in plan.units] == [4, 4]
    assert plan.section_kind == "numdot"


def test_bare_numbered_chapters_are_recognised():
    plan = plan_for("book_numbered_dot")
    assert plan.chapter_kind == "numbered_dot"
    assert len(plan.chapter_matches) == 5
    assert plan.section_kind == "numdot"


def test_headingless_book_degrades_gracefully():
    """No headings must still yield a studied structure, never an exception."""
    plan = plan_for("book_no_headings")
    assert len(plan.chapter_matches) >= 2
    assert plan.section_kind == "chunk"
    chunks = BookStructurer.chunk_text(book_no_headings(), target_chars=4000, max_chunks=6)
    assert 2 <= len(chunks) <= 6
    assert all(chunk.strip() for chunk in chunks)


def test_front_matter_toc_is_never_a_chapter():
    """Headings listed in the TOC are dropped in favour of the body copies."""
    plan = plan_for("book_openstax")
    text = book_openstax()
    positions = [spot.pos for spot in plan.chapter_matches]
    assert positions == sorted(positions)
    for spot in plan.chapter_matches:
        tail = text[spot.pos:spot.pos + 60]
        assert "Topic number" not in tail          # not a TOC section line


def test_section_starts_use_the_detected_family():
    text = book_numbered_dot()
    structurer = BookStructurer(text)
    plan = structurer.plan()
    body = text.split("\n1. Chapter topic 1\n", 1)[1].split("\n2. Chapter topic 2")[0]
    starts = structurer.section_starts(body, 1, plan)
    labels = [label for _idx, label, _title in starts]
    assert labels[:2] == ["1.1", "1.2"]
    assert all(title for _idx, _label, title in starts)


def test_helpers():
    assert roman_to_int("XIV") == 14
    assert roman_to_int("not-roman") is None
    assert word_to_int("Twenty Three") == 23
    assert word_to_int("Eleven") == 11
    assert word_to_int("zero") is None
    assert slugify("College Physics 2e (OpenStax)") == "college_physics_2e_openstax"
    assert slugify("") == "book"


# --------------------------------------------------------------------------- #
# Selective, resumable synthesis (10 out of 41 chapters, etc.)
# --------------------------------------------------------------------------- #
AVAILABLE = list(range(1, 42))          # a 41-chapter book


def test_selection_none_and_all_mean_everything():
    assert parse_chapter_selection(None, AVAILABLE) is None
    assert parse_chapter_selection("", AVAILABLE) is None
    assert parse_chapter_selection("all", AVAILABLE) is None
    assert parse_chapter_selection("full", AVAILABLE) is None


def test_selection_count_takes_the_first_n():
    assert parse_chapter_selection(10, AVAILABLE) == list(range(1, 11))
    assert parse_chapter_selection("10", AVAILABLE) == list(range(1, 11))
    assert parse_chapter_selection(41, AVAILABLE) == AVAILABLE


def test_selection_ranges_and_lists():
    assert parse_chapter_selection("1-10", AVAILABLE) == list(range(1, 11))
    assert parse_chapter_selection("1,3,5-8", AVAILABLE) == [1, 3, 5, 6, 7, 8]
    assert parse_chapter_selection("7, 3 ,1", AVAILABLE) == [1, 3, 7]      # sorted
    assert parse_chapter_selection([4, 2, 2], AVAILABLE) == [2, 4]         # deduped


def test_selection_never_silently_builds_nothing():
    """Out-of-range counts clamp, and a junk spec falls back to the whole book."""
    assert parse_chapter_selection("40-50", AVAILABLE) == [40, 41]         # clamped
    # "99" reads as "the first 99 chapters" -> the whole 41-chapter book.
    assert parse_chapter_selection("99", AVAILABLE) == AVAILABLE
    assert parse_chapter_selection("garbage", AVAILABLE) is None            # fallback = all
    assert parse_chapter_selection(0, AVAILABLE) is None                    # 0 == all
    assert parse_chapter_selection("", AVAILABLE) is None


def test_summarise_selection_is_readable():
    assert summarise_selection([1, 2, 3, 4, 5, 9], 41) == "chapters 1-5, 9 (6 of 41)"
    assert "6 of 41" in summarise_selection(list(range(1, 7)), 41)
    assert "nothing" in summarise_selection([], 41)


def test_estimate_scales_with_chapter_count():
    assert estimate_llm_build(10)["seconds"] == 250
    assert estimate_llm_build(41)["minutes"] > estimate_llm_build(10)["minutes"]


def _fake_chapters(count):
    return [{"chapter_index": i, "title": f"Chapter {i}",
             "theory_source": "llm" if i <= 3 else "deterministic"}
            for i in range(1, count + 1)]


def test_plan_chapters_selects_a_subset():
    divider = SmartBookDivider(text=book_numbered_dot(), title="T")
    chapters = _fake_chapters(41)
    assert divider.plan_chapters(chapters, "10") == list(range(1, 11))
    assert divider.plan_chapters(chapters, "1-5,9") == [1, 2, 3, 4, 5, 9]
    assert len(divider.plan_chapters(chapters, None)) == 41


def test_resume_skips_already_enriched_chapters():
    """The key accuracy guarantee: continue-later never repeats expensive work."""
    divider = SmartBookDivider(text=book_numbered_dot(), title="T")
    chapters = _fake_chapters(41)          # chapters 1-3 already Llama-enriched
    remaining = divider.plan_chapters(chapters, "1-10", resume=True)
    assert remaining == [4, 5, 6, 7, 8, 9, 10]      # 1-3 skipped, not redone
    # Without resume the same request redo_s every selected chapter.
    assert divider.plan_chapters(chapters, "1-10", resume=False) == list(range(1, 11))
    # Resuming a fully-enriched selection is a no-op.
    done = [{"chapter_index": i, "theory_source": "llm"} for i in range(1, 11)]
    assert divider.plan_chapters(done, "1-10", resume=True) == []


def test_theory_coverage_reports_partial_builds():
    divider = SmartBookDivider(text=book_numbered_dot(), title="T")
    coverage = divider.theory_coverage(_fake_chapters(41))
    assert coverage["enriched_count"] == 3
    assert coverage["chapters_total"] == 41
    assert coverage["pending_count"] == 38
    assert coverage["complete"] is False
    full = [{"chapter_index": i, "theory_source": "llm"} for i in range(1, 4)]
    assert divider.theory_coverage(full)["complete"] is True

