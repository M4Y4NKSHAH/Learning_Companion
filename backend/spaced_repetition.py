import os
import json
import datetime
from typing import Dict, List, Any, Optional

SRS_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "srs")
os.makedirs(SRS_DATA_DIR, exist_ok=True)


class SpacedRepetitionManager:
    """
    Implements the SuperMemo-2 (SM-2) algorithm for adaptive flashcard scheduling.
    Tracks repetition counts, inter-repetition intervals (days), and easiness factors
    to maximize long-term student memory retention.
    """

    @staticmethod
    def _get_student_file(student_id: str) -> str:
        safe_id = "".join(c for c in student_id if c.isalnum() or c in ("-", "_")) or "default_student"
        return os.path.join(SRS_DATA_DIR, f"{safe_id}.json")

    @classmethod
    def _load_student_schedule(cls, student_id: str) -> Dict[str, Any]:
        file_path = cls._get_student_file(student_id)
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[SRS] Warning loading schedule for {student_id}: {e}")
        return {"student_id": student_id, "cards": {}}

    @classmethod
    def _save_student_schedule(cls, student_id: str, data: Dict[str, Any]) -> None:
        file_path = cls._get_student_file(student_id)
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[SRS] Warning saving schedule for {student_id}: {e}")

    @classmethod
    def record_review(
        cls,
        student_id: str,
        card_id: str,
        quality: int,
        course_id: Optional[str] = None,
        chapter_id: Optional[str] = None,
        card_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Updates a card's SM-2 schedule based on student recall quality.
        quality: 0 (blackout) to 5 (perfect immediate recall).
        >= 3 is considered successful recall.
        """
        quality = max(0, min(5, quality))
        schedule = cls._load_student_schedule(student_id)
        cards = schedule.setdefault("cards", {})

        now = datetime.datetime.now(datetime.timezone.utc)
        today_date = now.date()

        record = cards.get(card_id, {
            "card_id": card_id,
            "course_id": course_id or "",
            "chapter_id": chapter_id or "",
            "repetitions": 0,
            "interval_days": 1,
            "easiness_factor": 2.5,
            "history": [],
            "next_review": today_date.isoformat(),
            "last_review": None,
            "card_data": card_data or {}
        })

        if card_data:
            record["card_data"] = card_data
        if course_id:
            record["course_id"] = course_id
        if chapter_id:
            record["chapter_id"] = chapter_id

        reps = record.get("repetitions", 0)
        interval = record.get("interval_days", 1)
        ef = record.get("easiness_factor", 2.5)

        # SM-2 Algorithm computation
        if quality >= 3:
            if reps == 0:
                interval = 1
            elif reps == 1:
                interval = 6
            else:
                interval = max(1, int(round(interval * ef)))
            reps += 1
        else:
            reps = 0
            interval = 1

        # Update Easiness Factor: EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
        ef_delta = 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
        ef = max(1.3, round(ef + ef_delta, 3))

        next_review_date = today_date + datetime.timedelta(days=interval)

        record["repetitions"] = reps
        record["interval_days"] = interval
        record["easiness_factor"] = ef
        record["last_review"] = today_date.isoformat()
        record["next_review"] = next_review_date.isoformat()
        record.setdefault("history", []).append({
            "timestamp": now.isoformat(),
            "quality": quality,
            "interval_days": interval,
            "easiness_factor": ef
        })

        cards[card_id] = record
        cls._save_student_schedule(student_id, schedule)

        return {
            "status": "success",
            "card_id": card_id,
            "repetitions": reps,
            "interval_days": interval,
            "easiness_factor": ef,
            "next_review": record["next_review"]
        }

    @classmethod
    def get_due_cards(cls, student_id: str, course_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns all flashcards scheduled for review on or before today."""
        schedule = cls._load_student_schedule(student_id)
        cards = schedule.get("cards", {})
        today_str = datetime.date.today().isoformat()

        due = []
        for card_id, info in cards.items():
            if course_id and info.get("course_id") and info.get("course_id") != course_id:
                continue
            next_rev = info.get("next_review", today_str)
            if next_rev <= today_str:
                due.append(info)

        # Sort by urgency (oldest due date first)
        due.sort(key=lambda x: x.get("next_review", today_str))
        return due

    @classmethod
    def get_student_stats(cls, student_id: str) -> Dict[str, Any]:
        """Calculates retention rate, total cards learned, and mature cards."""
        schedule = cls._load_student_schedule(student_id)
        cards = schedule.get("cards", {})
        total_cards = len(cards)
        if total_cards == 0:
            return {
                "total_cards": 0,
                "due_today": 0,
                "mature_cards": 0,
                "learning_cards": 0,
                "avg_easiness": 2.5
            }

        today_str = datetime.date.today().isoformat()
        due_count = sum(1 for c in cards.values() if c.get("next_review", today_str) <= today_str)
        mature_count = sum(1 for c in cards.values() if c.get("interval_days", 1) >= 21)
        learning_count = total_cards - mature_count
        avg_ef = round(sum(c.get("easiness_factor", 2.5) for c in cards.values()) / total_cards, 2)

        return {
            "total_cards": total_cards,
            "due_today": due_count,
            "mature_cards": mature_count,
            "learning_cards": learning_count,
            "avg_easiness": avg_ef
        }
