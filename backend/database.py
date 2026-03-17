"""
SQLite storage for classification events and feedback. Stays local to avoid AWS DB cost.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

from config import DATABASE_PATH


def _conn():
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DATABASE_PATH)


def init_db():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                item_name TEXT,
                predicted_category TEXT,
                final_category TEXT,
                confidence REAL,
                decision_mode TEXT,
                had_clarification INTEGER,
                was_correct INTEGER,
                raw_json TEXT
            )
        """)
        c.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)
        """)


def log_event(
    interaction_id: str,
    item_name: str,
    predicted_category: str,
    final_category: str,
    confidence: float,
    decision_mode: str,
    had_clarification: bool,
    was_correct: bool | None = None,
):
    import datetime
    raw = {
        "interaction_id": interaction_id,
        "item_name": item_name,
        "predicted_category": predicted_category,
        "final_category": final_category,
        "confidence": confidence,
        "decision_mode": decision_mode,
        "had_clarification": had_clarification,
        "was_correct": was_correct,
    }
    with _conn() as c:
        c.execute(
            """
            INSERT OR REPLACE INTO events
            (id, timestamp, item_name, predicted_category, final_category, confidence, decision_mode, had_clarification, was_correct, raw_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                interaction_id,
                datetime.datetime.utcnow().isoformat() + "Z",
                item_name,
                predicted_category,
                final_category,
                confidence,
                decision_mode,
                1 if had_clarification else 0,
                1 if was_correct else 0 if was_correct is False else None,
                json.dumps(raw),
            ),
        )


def record_feedback(interaction_id: str, final_category: str, was_correct: bool):
    """Update existing event with user feedback (final_category and was_correct)."""
    with _conn() as c:
        c.execute(
            """
            UPDATE events SET final_category = ?, was_correct = ? WHERE id = ?
            """,
            (final_category, 1 if was_correct else 0, interaction_id),
        )


def get_stats() -> dict:
    with _conn() as c:
        total = c.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        with_feedback = c.execute("SELECT COUNT(*) FROM events WHERE was_correct IS NOT NULL").fetchone()[0]
        correct = c.execute("SELECT COUNT(*) FROM events WHERE was_correct = 1").fetchone()[0]
        diverted = c.execute("SELECT COUNT(*) FROM events WHERE final_category IN ('RECYCLING','COMPOST')").fetchone()[0]
    accuracy = (correct / with_feedback) if with_feedback else 0.0
    # Per-category accuracy (only events with feedback)
    with _conn() as c:
        rows = c.execute(
            """
            SELECT final_category, SUM(CASE WHEN was_correct=1 THEN 1 ELSE 0 END), COUNT(*)
            FROM events WHERE was_correct IS NOT NULL
            GROUP BY final_category
            """
        ).fetchall()
    acc_per = {row[0]: round(row[1] / row[2], 2) if row[2] else 0 for row in rows}
    # Confusion: predicted vs final (3x3)
    with _conn() as c:
        pairs = c.execute(
            """
            SELECT predicted_category, final_category, COUNT(*)
            FROM events WHERE was_correct IS NOT NULL
            GROUP BY predicted_category, final_category
            """
        ).fetchall()
    cats = ["WASTE", "RECYCLING", "COMPOST"]
    ci = {x: i for i, x in enumerate(cats)}
    confusion = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
    for pred, fin, cnt in pairs:
        if pred in ci and fin in ci:
            confusion[ci[pred]][ci[fin]] = cnt
    # Top confusing items
    with _conn() as c:
        top = [{"item": r[0], "correct_rate": round(1 - (r[1] / r[2]), 2) if r[2] else 0} for r in c.execute(
            """
            SELECT item_name, SUM(CASE WHEN was_correct=0 THEN 1 ELSE 0 END), COUNT(*)
            FROM events WHERE was_correct IS NOT NULL
            GROUP BY item_name HAVING COUNT(*) >= 2
            ORDER BY SUM(CASE WHEN was_correct=0 THEN 1 ELSE 0 END) DESC
            LIMIT 10
            """
        ).fetchall()]
    return {
        "total_items": total,
        "accuracy_overall": round(accuracy, 2),
        "accuracy_per_category": acc_per,
        "confusion_matrix": confusion,
        "top_confusing_items": top,
        "items_diverted_from_landfill": diverted,
    }


def generate_interaction_id() -> str:
    return str(uuid.uuid4())
