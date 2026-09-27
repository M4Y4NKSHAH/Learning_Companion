"""
CLI Dynamic Ingestion & Training Harvester
Allows learners or administrators to ingest any real ebook (PDF, EPUB, MOBI, TXT, MD)
directly from their terminal. Automatically executes:
1. Document extraction (via PyMuPDF)
2. Dynamic chapter outline decomposition
3. Content-aware theory summarization & flashcard synthesis
4. Hybrid ChromaDB vector + BM25 indexing
5. Automatic export to training dataset (edu_finetune_dataset.jsonl)
"""

import os
import sys
import json
import argparse
from typing import Optional

# Ensure backend directory is in path
backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from material_parser import MaterialParser
from app import process_and_ingest_material

TRAINING_DATASET_PATH = os.path.join(
    os.path.dirname(backend_dir), "training", "edu_finetune_dataset.jsonl"
)

SYSTEM_PROMPT_CURRICULUM = (
    "You are an expert academic curriculum architect and cognitive scientist. "
    "When provided with a textbook section or ebook chapter, produce a strictly valid JSON "
    "object containing: 'summary' (2-3 sentence rigorous theoretical synthesis of foundational mechanics), "
    "'objectives' (array of 3 distinct learning objectives), and 'cards' (3 high-retention flashcards "
    "with 'topic', 'question', and structured 'answer' citing the core axioms). Respond ONLY with raw JSON."
)


def append_course_to_training_dataset(course: dict, subject: str):
    """Appends synthesized course chapters to the fine-tuning dataset immediately."""
    os.makedirs(os.path.dirname(TRAINING_DATASET_PATH), exist_ok=True)
    new_samples = 0
    with open(TRAINING_DATASET_PATH, "a", encoding="utf-8") as out:
        for ch in course.get("chapters", []):
            content = ch.get("full_text", "")
            title = ch.get("title", "Chapter")
            if len(content) < 200:
                continue

            output_obj = {
                "summary": ch.get("summary", ""),
                "objectives": ch.get("objectives", []),
                "cards": ch.get("cards", []),
                "deep_theory": ch.get("deep_theory", {})
            }

            sample = {
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT_CURRICULUM},
                    {"role": "user", "content": f"Subject: {subject}\nChapter: {title}\n\nChapter Content:\n{content[:2200]}"},
                    {"role": "assistant", "content": json.dumps(output_obj, ensure_ascii=False)}
                ]
            }
            out.write(json.dumps(sample, ensure_ascii=False) + "\n")
            new_samples += 1

    print(f"[Training] Appended {new_samples} authentic chapter pairs to {os.path.basename(TRAINING_DATASET_PATH)}")


def main():
    parser = argparse.ArgumentParser(
        description="Ingest any ebook (PDF, EPUB, MOBI, TXT, MD) dynamically into Learning Companion."
    )
    parser.add_argument("file_path", help="Path to the ebook or curriculum document on disk.")
    parser.add_argument("--subject", default=None, help="Subject (e.g. 'History', 'Economics', 'Law', 'Physics').")
    parser.add_argument("--tier", default="Standard", help="Academic tier (e.g. 'Introductory', 'Standard', 'Advanced').")
    parser.add_argument("--title", default=None, help="Course title (defaults to filename).")
    parser.add_argument("--skip-training", action="store_true", help="Skip appending to training dataset.")

    args = parser.parse_args()

    if not os.path.exists(args.file_path):
        print(f"Error: File not found: {args.file_path}")
        sys.exit(1)

    # Inferred parameters
    filename = os.path.basename(args.file_path)
    base_name = os.path.splitext(filename)[0]
    title = args.title or base_name.replace("_", " ").replace("-", " ").title()
    subject = args.subject or base_name.split("_")[0].title()

    print(f"\n=======================================================")
    print(f"DYNAMIC EBOOK INGESTION: {filename}")
    print(f"Course Title: {title} | Subject: {subject} | Tier: {args.tier}")
    print(f"=======================================================")

    print(f"[1/4] Extracting text and structure from {filename}...")
    raw_text = MaterialParser.extract_text_from_file(args.file_path)
    print(f"Extracted {len(raw_text):,} characters.")

    print(f"[2/4] Executing dynamic chapter decomposition & synthesis...")
    course = process_and_ingest_material(
        title=title,
        subject=subject,
        academic_tier=args.tier,
        raw_text=raw_text
    )

    chapters = course.get("chapters", [])
    print(f"[3/4] Successfully generated course '{course['title']}' ({course['id']}):")
    print(f"      - {len(chapters)} Chapters identified and summarized")
    total_cards = sum(len(ch.get("cards", [])) for ch in chapters)
    print(f"      - {total_cards} Content-grounded flashcards created")
    print(f"      - Indexed in ChromaDB with BM25 hybrid search")

    if not args.skip_training:
        print(f"[4/4] Updating local fine-tuning dataset...")
        append_course_to_training_dataset(course, subject)
    else:
        print(f"[4/4] Skipping fine-tuning dataset export.")

    print(f"\n[DONE] Course is live and ready for interactive learning in the web UI!")


if __name__ == "__main__":
    main()
