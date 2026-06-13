"""SQLite storage for notifications. Also tracks which emails we've already processed so we don't classify them again."""
from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import List

from .models import Category, Classification, Email, Notification, Priority

log = logging.getLogger("storage")

_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "agent.db"
_lock = threading.Lock()


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    log.info("setting up database at %s", _DB_PATH)
    with _lock, _connect() as conn:
        # tracks every email we've processed so we don't classify it again
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_emails (
                id          TEXT PRIMARY KEY,
                processed_at TEXT NOT NULL
            )
            """
        )
        # only important emails get stored here and shown on the dashboard
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id            TEXT PRIMARY KEY,
                sender        TEXT NOT NULL,
                subject       TEXT NOT NULL,
                priority      TEXT NOT NULL,
                category      TEXT NOT NULL,
                reason        TEXT NOT NULL,
                received_at   TEXT NOT NULL,
                classified_by TEXT NOT NULL
            )
            """
        )


def is_processed(email_id: str) -> bool:
    """Check if we've already processed this email."""
    with _lock, _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM processed_emails WHERE id = ?", (email_id,)
        ).fetchone()
        return row is not None


def mark_processed(email_id: str) -> None:
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO processed_emails (id, processed_at) VALUES (?, ?)",
            (email_id, datetime.utcnow().isoformat()),
        )


def save_notification(email: Email, result: Classification) -> None:
    log.info("saving to dashboard — priority=%s  category=%s  subject=%r",
             result.priority.value, result.category.value, email.subject)
    with _lock, _connect() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO notifications
              (id, sender, subject, priority, category, reason, received_at, classified_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                email.id,
                email.from_,
                email.subject,
                result.priority.value,
                result.category.value,
                result.reason,
                email.received_at.isoformat(),
                result.classified_by,
            ),
        )


def get_notifications() -> List[Notification]:
    """Get all notifications sorted by priority (HIGH first), then by most recent."""
    priority_rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    with _lock, _connect() as conn:
        rows = conn.execute("SELECT * FROM notifications").fetchall()

    notes = [
        Notification(
            id=r["id"],
            **{"from": r["sender"]},
            subject=r["subject"],
            priority=Priority(r["priority"]),
            category=Category(r["category"]),
            reason=r["reason"],
            received_at=datetime.fromisoformat(r["received_at"]),
            classified_by=r["classified_by"],
        )
        for r in rows
    ]
    notes.sort(key=lambda n: (priority_rank[n.priority.value], n.received_at), reverse=False)
    notes.sort(key=lambda n: (priority_rank[n.priority.value], -n.received_at.timestamp()))
    return notes


def stats() -> dict:
    with _lock, _connect() as conn:
        seen = conn.execute("SELECT COUNT(*) c FROM processed_emails").fetchone()["c"]
        important = conn.execute("SELECT COUNT(*) c FROM notifications").fetchone()["c"]
    return {"total_processed": seen, "important": important, "ignored": seen - important}
