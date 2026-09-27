import os
import json
import re
from typing import List, Dict, Any

COURSES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend", "data", "courses")
OUTPUT_JSONL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "edu_finetune_dataset.jsonl")

SYSTEM_PROMPT_CURRICULUM = (
    "You are an expert academic curriculum architect and cognitive scientist. "
    "When provided with a chapter title and textbook content, produce a strictly valid JSON "
    "object containing: 'summary' (2-3 sentence rigorous theoretical synthesis), 'objectives' (3 items), "
    "and 'cards' (3 high-retention flashcards with 'topic', 'question', and structured 'answer'). "
    "Respond ONLY with raw JSON."
)

SYSTEM_PROMPT_ASSESSMENT = (
    "You are a master academic assessment author. When provided with chapter theory and concepts, "
    "produce a strictly valid JSON object with: 'quizzes' (concept-grounded multiple choice questions "
    "with options, answer, and misconception), and 'finalExam' (rigorous short-answer calculation/principle "
    "problems with expected answer, formula, and misconception). Respond ONLY with raw JSON."
)


def clean_context_sample(text: str, max_chars: int = 2400) -> str:
    """Cleans text of excessive whitespace and truncates safely at sentence boundary."""
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    truncated = cleaned[:max_chars]
    last_period = truncated.rfind(".")
    if last_period > max_chars - 300:
        return truncated[:last_period + 1]
    return truncated


def build_curriculum_example(title: str, content: str, summary: str, objectives: list, cards: list, deep_theory: dict = None) -> Dict[str, Any]:
    output_obj = {
        "summary": summary,
        "objectives": objectives[:3] if objectives else [f"Understand {title}"],
        "cards": [
            {
                "topic": c.get("topic", title),
                "question": c.get("question", f"What is the key principle of {title}?"),
                "answer": c.get("answer", "• Governing axiom and mechanical application.")
            }
            for c in cards[:3]
        ]
    }
    if deep_theory:
        output_obj["deep_theory"] = deep_theory

    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_CURRICULUM},
            {
                "role": "user",
                "content": f"Title: {title}\n\nChapter Content:\n{clean_context_sample(content)}"
            },
            {
                "role": "assistant",
                "content": json.dumps(output_obj, ensure_ascii=False)
            }
        ]
    }


def build_assessment_example(title: str, quizzes: list, final_exams: list) -> Dict[str, Any]:
    output_obj = {
        "quizzes": quizzes[:2] if quizzes else [],
        "finalExam": final_exams[:2] if final_exams else []
    }
    return {
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT_ASSESSMENT},
            {
                "role": "user",
                "content": f"Generate summative assessment questions for course module: '{title}'."
            },
            {
                "role": "assistant",
                "content": json.dumps(output_obj, ensure_ascii=False)
            }
        ]
    }


def main():
    if not os.path.exists(COURSES_DIR):
        print(f"Courses directory not found: {COURSES_DIR}")
        return

    examples = []
    course_files = [f for f in os.listdir(COURSES_DIR) if f.endswith(".json")]
    print(f"Scanning {len(course_files)} course files for fine-tuning data...")

    for fname in course_files:
        fpath = os.path.join(COURSES_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                course = json.load(f)
        except Exception as e:
            print(f"Skipping {fname}: {e}")
            continue

        course_title = course.get("title", "Course")
        chapters = course.get("chapters", [])
        quizzes = course.get("quizzes", [])
        final_exams = course.get("finalExam", [])

        # 1. Add curriculum extraction examples per chapter
        for ch in chapters:
            content = ch.get("full_text") or ch.get("content") or ""
            if len(content) < 120:
                continue

            summary = ch.get("summary", "")
            cards = ch.get("cards", [])
            objectives = ch.get("objectives", [])
            deep_theory = ch.get("deep_theory")

            if summary and cards:
                ex = build_curriculum_example(
                    title=ch.get("title", "Chapter"),
                    content=content,
                    summary=summary,
                    objectives=objectives,
                    cards=cards,
                    deep_theory=deep_theory
                )
                examples.append(ex)

        # 2. Add assessment pair if quizzes or final exams exist
        if quizzes or final_exams:
            ass_ex = build_assessment_example(course_title, quizzes, final_exams)
            examples.append(ass_ex)

    os.makedirs(os.path.dirname(OUTPUT_JSONL), exist_ok=True)
    with open(OUTPUT_JSONL, "w", encoding="utf-8") as out_f:
        for ex in examples:
            out_f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    print(f"Successfully generated {len(examples)} fine-tuning examples saved to:")
    print(f" -> {OUTPUT_JSONL}")


if __name__ == "__main__":
    main()
