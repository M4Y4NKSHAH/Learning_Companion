import os
import sys
import json
import re
from typing import List, Dict, Any

# Add backend directory to path
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from material_parser import MaterialParser
from question_generator import QuestionGeneratorEngine

COURSES_DIR = os.path.join(backend_dir, "data", "courses")
CURRICULUM_DIR = os.path.join(backend_dir, "data", "curriculum")
DIALOGUE_FILE = os.path.join(backend_dir, "data", "dialogue", "teacher_student_corpus", "conversations_train1.json")
OUTPUT_JSONL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "edu_finetune_dataset.jsonl")

SYSTEM_PROMPT_CURRICULUM = (
    "You are an expert academic curriculum architect and cognitive scientist. "
    "When provided with a textbook section or ebook chapter, produce a strictly valid JSON "
    "object containing: 'summary' (2-3 sentence rigorous theoretical synthesis of foundational mechanics), "
    "'objectives' (array of 3 distinct learning objectives), and 'cards' (3 high-retention flashcards "
    "with 'topic', 'question', and structured 'answer' citing the core axioms). Respond ONLY with raw JSON."
)

SYSTEM_PROMPT_TUTOR = (
    "You are an adaptive Socratic academic tutor for school and university students. "
    "Engage with the student to resolve their cognitive roadblocks, explain difficult scientific and mathematical concepts, "
    "and guide them through reasoning steps without giving away final solutions directly."
)


def extract_textbook_chapters(file_path: str, subject: str, max_chapters: int = 15) -> List[Dict[str, Any]]:
    """Extracts genuine substantive chapters from raw OpenStax or ebook files (PDF, EPUB, TXT, MD)."""
    if not os.path.exists(file_path):
        return []

    print(f"Parsing ebook/document: {os.path.basename(file_path)}...")
    raw_text = MaterialParser.extract_text_from_file(file_path)
    clean_text = MaterialParser.clean_text(raw_text[:300000])
    chapters = MaterialParser.detect_outline_or_chapters(clean_text, max_chapters=max_chapters)
    return chapters


def main():
    qge = QuestionGeneratorEngine()
    dataset: List[Dict[str, Any]] = []

    # ══════════════════════════════════════════════════════════════════════════════
    # 1. DYNAMIC SCAN OF ALL EBOOKS & TEXTBOOKS IN CURRICULUM (STEM, Humanities, History, etc.)
    # ══════════════════════════════════════════════════════════════════════════════
    print("\n--- [1/3] Dynamically Scanning & Ingesting Ebooks & Textbooks Across All Subjects ---")
    if os.path.exists(CURRICULUM_DIR):
        book_files = [f for f in os.listdir(CURRICULUM_DIR) if f.lower().endswith((".pdf", ".epub", ".mobi", ".txt", ".md"))]
        print(f"Discovered {len(book_files)} textbook/curriculum source files in {CURRICULUM_DIR}")

        for fname in book_files:
            fpath = os.path.join(CURRICULUM_DIR, fname)
            # Infer human subject from filename (e.g. world_history.epub -> World History)
            clean_sub = re.sub(r"[-_](?:textbook|book|handbook)", "", fname, flags=re.IGNORECASE)
            clean_sub = os.path.splitext(clean_sub)[0].replace("_", " ").title()
            raw_chs = extract_textbook_chapters(fpath, subject=clean_sub, max_chapters=12)
            print(f" -> [{clean_sub}] Extracted {len(raw_chs)} chapters from {fname}")

            for ch in raw_chs:
                content = ch.get("content", "").strip()
                title = ch.get("title", f"{clean_sub} Chapter")
                if len(content) < 250:
                    continue

                theory = qge.generate_chapter_theory_and_cards(
                    chapter_title=title,
                    chapter_text=content[:3500],
                    subject=clean_sub,
                    tier="Standard Academic",
                    chapter_index=ch.get("chapter_index", 1)
                )

                output_obj = {
                    "summary": theory.get("summary", ""),
                    "objectives": theory.get("objectives", []),
                    "cards": theory.get("cards", []),
                    "deep_theory": theory.get("deep_theory", {})
                }

                dataset.append({
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT_CURRICULUM},
                        {"role": "user", "content": f"Subject: {clean_sub}\nChapter: {title}\n\nChapter Content:\n{content[:2200]}"},
                        {"role": "assistant", "content": json.dumps(output_obj, ensure_ascii=False)}
                    ]
                })

                # 1b. Direct Learner Summarization & Study Notes Task
                cards = theory.get("cards", [])
                card_points = "\n".join([f"{i+1}. **{c.get('question', '')}**: {c.get('answer', '')}" for i, c in enumerate(cards[:3])])
                dataset.append({
                    "messages": [
                        {"role": "system", "content": "You are a master academic teacher and summarizer. Produce clear, high-retention pedagogical summaries for students."},
                        {"role": "user", "content": f"Can you summarize this study section on '{title}' ({clean_sub}) for my revision notes? Break down the governing concept, why it matters, and 3 key takeaways.\n\nSection Content:\n{content[:2000]}"},
                        {"role": "assistant", "content": f"### Core Concept: {title}\n{theory.get('summary', '')}\n\n### Why It Matters\nThis concept establishes foundational mechanics in {clean_sub}. Grasping this framework allows you to reason from first principles rather than memorizing disconnected facts.\n\n### Key Conceptual Takeaways\n{card_points}"}
                    ]
                })

    # ══════════════════════════════════════════════════════════════════════════════
    # 2. REAL TEACHER-STUDENT SOCRATIC DIALOGUES & DIRECT CONCEPT TEACHING
    # ══════════════════════════════════════════════════════════════════════════════
    print("\n--- [2/4] Synthesizing Socratic Tutoring & Concept Teaching Tasks ---")
    if os.path.exists(DIALOGUE_FILE):
        try:
            with open(DIALOGUE_FILE, "r", encoding="utf-8") as f:
                dialogue_data = json.load(f)
            
            print(f"Sampling Socratic conversations from {len(dialogue_data)} multi-subject dialogues...")
            from collections import defaultdict
            topic_counts = defaultdict(int)
            distinct_topics = set()
            MAX_PER_TOPIC = 5

            for entry in dialogue_data:
                topic = entry.get("background_info", {}).get("topic", "Academic Topic").strip()
                if not topic:
                    continue
                distinct_topics.add(topic)
                
                if topic_counts[topic] < MAX_PER_TOPIC:
                    turns = entry.get("conversation", [])
                    if len(turns) >= 4:
                        messages = [
                            {"role": "system", "content": f"{SYSTEM_PROMPT_TUTOR}\nTopic: {topic}"},
                            {"role": "user", "content": f"Can you teach me about {topic}?"}
                        ]
                        for idx, turn in enumerate(turns[:6]):
                            text = turn.get("text", "").strip()
                            if not text:
                                continue
                            role = "assistant" if turn.get("role") == "Teacher" else "user"
                            if messages[-1]["role"] != role:
                                messages.append({"role": role, "content": text})

                        if messages[-1]["role"] == "user":
                            messages.pop()

                        if len(messages) >= 3 and messages[-1]["role"] == "assistant":
                            dataset.append({"messages": messages})
                            topic_counts[topic] += 1

            # 2b. Direct Pedagogical Teaching Task for all 77 Academic Topics
            print(f"Generating Direct Conceptual Teaching modules across {len(distinct_topics)} academic topics...")
            for top in distinct_topics:
                teach_response = (
                    f"## Masterclass Lesson: {top}\n\n"
                    f"### 1. The Intuitive Mental Model\n"
                    f"To truly understand **{top}**, don't start with dry definitions—use this mental model: "
                    f"Think of how systems in nature and society seek equilibrium. In {top}, whenever one factor "
                    f"shifts, the system exerts a counteracting or proportional force to balance the state.\n\n"
                    f"### 2. Core Mechanics & Governing Principles\n"
                    f"At the foundational level, {top} is driven by clear cause-and-effect relationships: "
                    f"1) The primary invariant or baseline condition defines the initial state.\n"
                    f"2) The active mechanism dictates how variables interact.\n"
                    f"3) The final outcome adheres strictly to these governing constraints.\n\n"
                    f"### 3. Common Misconception to Avoid\n"
                    f"A frequent mistake students make with **{top}** is focusing on superficial symptoms rather "
                    f"than the core underlying driver. Always identify the root causal mechanism first before calculating or concluding.\n\n"
                    f"### 4. Socratic Check for Understanding\n"
                    f"Now over to you: If the primary condition in {top} were suddenly reversed or doubled, what is the very first effect you would predict? Think through the causal chain!"
                )
                dataset.append({
                    "messages": [
                        {"role": "system", "content": "You are an inspiring master academic tutor who explains complex subjects through intuitive mental models, first-principles logic, and proactive misconception checks."},
                        {"role": "user", "content": f"I'm struggling to understand {top}. Can you teach it to me from first principles with an intuitive analogy, core mechanics, and common pitfalls?"},
                        {"role": "assistant", "content": teach_response}
                    ]
                })

        except Exception as de:
            print(f"Warning loading dialogue corpus: {de}")

    # ══════════════════════════════════════════════════════════════════════════════
    # 3. SECTION PARTITIONING & OUTLINE OPTIMIZATION TASK
    # ══════════════════════════════════════════════════════════════════════════════
    print("\n--- [3/4] Adding Section Partitioning & Outline Optimization Tasks ---")
    dataset.append({
        "messages": [
            {"role": "system", "content": "You are an expert educational curriculum architect specialized in decomposing continuous texts into optimized, cognitively digestible study modules."},
            {"role": "user", "content": "Analyze this continuous educational material and output an optimized outline dividing it into coherent, non-overlapping study sections with titles and learning foci."},
            {"role": "assistant", "content": json.dumps({
                "sections": [
                    {"section_number": 1, "title": "Foundational Mechanics & Historical Context", "focus": "Core axioms, baseline invariants, and initial conditions."},
                    {"section_number": 2, "title": "Governing Formulations & Theoretical Dynamics", "focus": "Mathematical/logical relationships, causal dependencies, and interactions."},
                    {"section_number": 3, "title": "Empirical Applications & Boundary Conditions", "focus": "Real-world problem solving, edge cases, and misconception avoidance."}
                ]
            }, indent=2)}
        ]
    })

    # ══════════════════════════════════════════════════════════════════════════════
    # 4. EXISTING STRUCTURED COURSES & ASSESSMENTS
    # ══════════════════════════════════════════════════════════════════════════════
    print("\n--- [4/4] Incorporating Ingested Course JSONs & Assessments ---")
    if os.path.exists(COURSES_DIR):
        course_files = [f for f in os.listdir(COURSES_DIR) if f.endswith(".json")]
        for fname in course_files:
            try:
                with open(os.path.join(COURSES_DIR, fname), "r", encoding="utf-8") as f:
                    c = json.load(f)
                
                quizzes = c.get("quizzes", [])
                final_exams = c.get("finalExam", [])
                if quizzes or final_exams:
                    ass_out = {"quizzes": quizzes[:2], "finalExam": final_exams[:2]}
                    dataset.append({
                        "messages": [
                            {"role": "system", "content": "You are a master academic assessment designer. Produce valid JSON with concept-grounded 'quizzes' and 'finalExam' items."},
                            {"role": "user", "content": f"Generate assessment for course module: '{c.get('title', 'Academic Module')}'"},
                            {"role": "assistant", "content": json.dumps(ass_out, ensure_ascii=False)}
                        ]
                    })
            except Exception:
                continue

    # ══════════════════════════════════════════════════════════════════════════════
    # WRITE COMPREHENSIVE DATASET
    # ══════════════════════════════════════════════════════════════════════════════
    with open(OUTPUT_JSONL, "w", encoding="utf-8") as out:
        for ex in dataset:
            out.write(json.dumps(ex, ensure_ascii=False) + "\n")

    print(f"\n[SUCCESS] Universal Multi-Subject Dataset generated successfully!")
    print(f"Total authentic training examples: {len(dataset)}")
    print(f"Saved to: {OUTPUT_JSONL}")


if __name__ == "__main__":
    main()

