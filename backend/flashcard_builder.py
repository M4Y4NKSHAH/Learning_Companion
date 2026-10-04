import hashlib
import json
import os
import re
from typing import Optional

from database_ingest import DatabaseIngestPipeline
from theory_repo import FLASHCARD_REPOSITORY

BOILERPLATE_KEYWORDS = (
    "openstax",
    "isbn",
    "copyright",
    "rice university",
    "creativecommons",
    "access for free",
    "trademark",
    "philanthropic",
    "senior contributing",
    "original publication",
)

_flashcard_cache: dict[tuple[str, str], list[dict]] = {}
_gemini_flashcard_cache: dict[tuple[str, str], list[dict]] = {}


def _is_educational_content(text: str) -> bool:
    lower = text.lower()
    if len(text) < 90 or len(text) > 1400:
        return False
    if any(keyword in lower for keyword in BOILERPLATE_KEYWORDS):
        return False
    alpha_ratio = sum(ch.isalpha() for ch in text) / max(len(text), 1)
    return alpha_ratio > 0.55


def _extract_topic(text: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    first = sentences[0] if sentences else text[:90]

    definition_match = re.match(
        r"^(.{8,72}?)\s+(?:is|are|refers to|means|describes|defines)\s",
        first,
        re.IGNORECASE,
    )
    if definition_match:
        return definition_match.group(1).strip().strip('"')

    heading_match = re.match(r"^([A-Z][A-Za-z0-9\s\-,:()]{4,70})", first)
    if heading_match:
        return heading_match.group(1).strip()

    topic = first[:72].strip()
    return topic + ("..." if len(first) > 72 else "")


def _format_answer(text: str) -> str:
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", text.strip())
        if len(sentence.strip()) > 24
    ][:4]
    if not sentences:
        return f"• {text.strip()[:500]}"
    lines = []
    for sentence in sentences:
        line = sentence if sentence.endswith((".", "!", "?")) else f"{sentence}."
        lines.append(f"• {line}")
    return "\n".join(lines)


def _build_card_id(subject: str, tier: str, chunk_text: str) -> str:
    digest = hashlib.md5(chunk_text.encode("utf-8")).hexdigest()[:10]
    tier_slug = tier.replace(" ", "").replace("-", "").lower()
    subject_slug = subject[:3].lower()
    return f"ch_{subject_slug}_{tier_slug}_{digest}"


def build_flashcards_from_chroma(
    subject: str,
    tier: str,
    max_cards: int = 3,
    pipeline: Optional[DatabaseIngestPipeline] = None,
) -> list[dict]:
    """Fetch textbook chunks from ChromaDB and convert them into study flashcards heuristically."""
    cache_key = (subject, tier)
    if cache_key in _flashcard_cache:
        return _flashcard_cache[cache_key][:max_cards]

    cards: list[dict] = []
    try:
        db = pipeline or DatabaseIngestPipeline()
        results = db.curriculum_collection.query(
            query_texts=[f"{subject} core concepts {tier}"],
            n_results=12,
            where={"$and": [{"subject": subject}, {"academic_tier": tier}]},
        )
        documents = results.get("documents", [[]])[0] if results else []
    except Exception:
        documents = []

    seen_topics: set[str] = set()
    for chunk in documents:
        if not _is_educational_content(chunk):
            continue

        topic = _extract_topic(chunk)
        topic_key = topic.lower()
        if topic_key in seen_topics:
            continue
        seen_topics.add(topic_key)

        cards.append(
            {
                "id": _build_card_id(subject, tier, chunk),
                "topic": topic,
                "question": f"Explain the key ideas behind **{topic}** and how they apply in {subject}.",
                "answer": _format_answer(chunk),
                "source": "chromadb_heuristic",
            }
        )
        if len(cards) >= max_cards:
            break

    # If ChromaDB returned fewer than 3, backfill from theory repo static cards
    if len(cards) < max_cards:
        repo_cards = FLASHCARD_REPOSITORY.get(subject, {}).get(tier, {}).get("cards", [])
        for rc in repo_cards:
            if len(cards) >= max_cards:
                break
            if not any(c["id"] == rc["id"] for c in cards):
                cards.append(rc)

    cards = cards[:max_cards]
    _flashcard_cache[cache_key] = cards
    return cards


def generate_gemini_flashcards_from_chroma(
    subject: str,
    tier: str,
    pipeline: Optional[DatabaseIngestPipeline] = None,
) -> dict:
    """
    Generates EXACTLY 3 high-quality flashcards using Gemini from ChromaDB curriculum chunks.
    Implements in-memory caching per (subject, tier) to minimize token consumption.
    """
    cache_key = (subject, tier)

    # 1. Check in-memory cache
    if cache_key in _gemini_flashcard_cache:
        return {
            "cards": _gemini_flashcard_cache[cache_key],
            "cached": True,
            "source": "gemini_cache",
        }

    # 2. Retrieve ChromaDB context chunks
    retrieved_chunks = []
    try:
        db = pipeline or DatabaseIngestPipeline()
        results = db.curriculum_collection.query(
            query_texts=[f"Core curriculum concepts and theories of {subject} {tier}"],
            n_results=5,
            where={"$and": [{"subject": subject}, {"academic_tier": tier}]},
        )
        if results and results.get("documents"):
            retrieved_chunks = [
                doc for doc in results["documents"][0] if _is_educational_content(doc)
            ]
    except Exception as e:
        print(f"ChromaDB retrieval warning: {e}")

    context_text = "\n---\n".join(retrieved_chunks[:4]) if retrieved_chunks else f"Core textbook materials for {subject} ({tier})."

    # 3. Attempt Gemini generation
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    cards = []

    if api_key:
        try:
            from question_generator import normalize_ai_content
            model_name = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
            try:
                model = ChatGoogleGenerativeAI(
                    model=model_name, temperature=0.3, google_api_key=api_key
                )
            except Exception:
                model = ChatGoogleGenerativeAI(
                    model="gemini-2.5-flash", temperature=0.3, google_api_key=api_key
                )

            prompt = (
                f"You are an expert curriculum designer for {subject} ({tier}).\n"
                f"Based on the following verified textbook chunks:\n\n{context_text}\n\n"
                "Create EXACTLY 3 distinct, high-impact educational flashcards.\n"
                "Return ONLY a minified JSON array (no markdown code fences, no extra text) formatted as:\n"
                '[\n'
                '  {"id": "ai_1", "topic": "Short Topic Title", "question": "Clear, engaging concept question?", "answer": "• Key bullet point 1\\n• Key bullet point 2\\n• Key bullet point 3"},\n'
                '  {"id": "ai_2", "topic": "Short Topic Title", "question": "Clear, engaging concept question?", "answer": "• Key bullet point 1\\n• Key bullet point 2\\n• Key bullet point 3"},\n'
                '  {"id": "ai_3", "topic": "Short Topic Title", "question": "Clear, engaging concept question?", "answer": "• Key bullet point 1\\n• Key bullet point 2\\n• Key bullet point 3"}\n'
                ']'
            )

            response = model.invoke([HumanMessage(content=prompt)])
            raw_content = normalize_ai_content(response.content)
            clean_json = (
                raw_content.replace("```json", "")
                .replace("```", "")
                .strip()
            )
            parsed = json.loads(clean_json)

            if isinstance(parsed, list) and len(parsed) >= 1:
                for idx, c in enumerate(parsed[:3], 1):
                    cards.append(
                        {
                            "id": f"ai_{subject[:3].lower()}_{tier[:3].lower()}_{idx}",
                            "topic": str(c.get("topic", f"{subject} Core Topic {idx}")),
                            "question": str(c.get("question", "What is the key concept?")),
                            "answer": str(c.get("answer", "• Key concept overview.")),
                            "source": "gemini_rag",
                        }
                    )
        except Exception as e:
            print(f"Gemini flashcard generation fallback triggered: {e}")

    # 4. Fallback if Gemini failed or no API key available
    if len(cards) < 3:
        cards = build_flashcards_from_chroma(subject, tier, max_cards=3)

    cards = cards[:3]

    # 5. Store in cache
    _gemini_flashcard_cache[cache_key] = cards

    return {
        "cards": cards,
        "cached": False,
        "source": "gemini_rag",
    }

