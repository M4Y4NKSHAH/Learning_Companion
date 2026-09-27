import os
import sqlite3
import datetime
from typing import Dict, List, Any, Optional

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, "analytics.db")


class AnalyticsDatabase:
    """
    Persistent SQLite-backed analytics store tracking student mastery curves,
    per-chapter performance heatmaps, attempt histories, and hint ladder utilization.
    """

    @classmethod
    def _get_connection(cls) -> sqlite3.Connection:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    @classmethod
    def init_db(cls) -> None:
        """Initializes tables and indexes if they do not exist."""
        with cls._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS student_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT NOT NULL,
                    course_id TEXT,
                    chapter_id TEXT,
                    question_id TEXT,
                    question_type TEXT,
                    is_correct INTEGER,
                    accuracy_pct REAL,
                    fuzzy_score REAL,
                    error_severity REAL,
                    hint_level INTEGER DEFAULT 1,
                    latency_seconds REAL,
                    timestamp TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chapter_mastery (
                    student_id TEXT NOT NULL,
                    course_id TEXT NOT NULL,
                    chapter_id TEXT NOT NULL,
                    total_attempts INTEGER DEFAULT 0,
                    correct_attempts INTEGER DEFAULT 0,
                    avg_fuzzy_score REAL DEFAULT 0.0,
                    mastery_level TEXT DEFAULT 'Developing',
                    last_updated TEXT NOT NULL,
                    PRIMARY KEY (student_id, course_id, chapter_id)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_attempts_student ON student_attempts(student_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_attempts_course ON student_attempts(course_id, chapter_id)")
            conn.commit()

    @classmethod
    def record_attempt(
        cls,
        student_id: str,
        course_id: Optional[str] = "",
        chapter_id: Optional[str] = "",
        question_id: Optional[str] = "",
        question_type: str = "short_answer",
        is_correct: bool = False,
        accuracy_pct: float = 0.0,
        fuzzy_score: float = 0.0,
        error_severity: float = 0.0,
        hint_level: int = 1,
        latency_seconds: float = 0.0
    ) -> None:
        """Records a single student assessment attempt and updates chapter mastery stats."""
        cls.init_db()
        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
        course_id = course_id or "general"
        chapter_id = chapter_id or "ch_1"

        with cls._get_connection() as conn:
            cursor = conn.cursor()
            # 1. Insert attempt
            cursor.execute("""
                INSERT INTO student_attempts (
                    student_id, course_id, chapter_id, question_id, question_type,
                    is_correct, accuracy_pct, fuzzy_score, error_severity,
                    hint_level, latency_seconds, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                student_id, course_id, chapter_id, question_id, question_type,
                1 if is_correct else 0, accuracy_pct, fuzzy_score, error_severity,
                hint_level, latency_seconds, now_str
            ))

            # 2. Update aggregated chapter mastery
            cursor.execute("""
                SELECT total_attempts, correct_attempts, avg_fuzzy_score
                FROM chapter_mastery
                WHERE student_id = ? AND course_id = ? AND chapter_id = ?
            """, (student_id, course_id, chapter_id))
            row = cursor.fetchone()

            if row:
                tot = row["total_attempts"] + 1
                corr = row["correct_attempts"] + (1 if is_correct else 0)
                new_avg = round(((row["avg_fuzzy_score"] * row["total_attempts"]) + fuzzy_score) / tot, 1)
            else:
                tot = 1
                corr = 1 if is_correct else 0
                new_avg = round(fuzzy_score, 1)

            # Determine mastery tier
            if new_avg >= 85.0 and (corr / tot) >= 0.8:
                tier = "High Mastery"
            elif new_avg >= 65.0:
                tier = "Moderate Mastery"
            else:
                tier = "Developing"

            cursor.execute("""
                INSERT OR REPLACE INTO chapter_mastery (
                    student_id, course_id, chapter_id, total_attempts,
                    correct_attempts, avg_fuzzy_score, mastery_level, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (student_id, course_id, chapter_id, tot, corr, new_avg, tier, now_str))

            conn.commit()

    @classmethod
    def get_course_mastery_heatmap(cls, student_id: str, course_id: str) -> List[Dict[str, Any]]:
        """Returns per-chapter mastery stats for a student on a specific course."""
        cls.init_db()
        with cls._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT chapter_id, total_attempts, correct_attempts, avg_fuzzy_score, mastery_level, last_updated
                FROM chapter_mastery
                WHERE student_id = ? AND course_id = ?
                ORDER BY chapter_id ASC
            """, (student_id, course_id))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    @classmethod
    def get_student_summary(cls, student_id: str) -> Dict[str, Any]:
        """Calculates overarching learner growth trajectory across all attempts."""
        cls.init_db()
        with cls._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_attempts,
                    SUM(is_correct) as correct_count,
                    AVG(fuzzy_score) as overall_avg_score,
                    AVG(latency_seconds) as avg_latency,
                    AVG(error_severity) as avg_severity
                FROM student_attempts
                WHERE student_id = ?
            """, (student_id,))
            row = cursor.fetchone()
            if not row or row["total_attempts"] == 0:
                return {
                    "student_id": student_id,
                    "total_attempts": 0,
                    "accuracy_rate": 0.0,
                    "avg_score": 0.0,
                    "avg_latency": 0.0,
                    "learning_trajectory": "New Student (No History)"
                }

            tot = row["total_attempts"]
            corr = row["correct_count"] or 0
            acc_rate = round((corr / tot) * 100, 1)
            avg_score = round(row["overall_avg_score"] or 0.0, 1)
            avg_lat = round(row["avg_latency"] or 0.0, 1)

            if acc_rate >= 80.0:
                traj = "Accelerated Mastery Trajectory"
            elif acc_rate >= 50.0:
                traj = "Steady Conceptual Growth"
            else:
                traj = "Foundational Remediation Recommended"

            return {
                "student_id": student_id,
                "total_attempts": tot,
                "accuracy_rate": acc_rate,
                "avg_score": avg_score,
                "avg_latency": avg_lat,
                "learning_trajectory": traj
            }
