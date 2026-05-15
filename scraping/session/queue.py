"""Persistent URL queue — SQLite-backed, survives process restarts."""

import logging
import sqlite3
from pathlib import Path

log = logging.getLogger(__name__)

_DEFAULT_DB = "scrape_queue.db"


class URLQueue:
    """SQLite-backed URL queue for resumable crawl sessions."""

    def __init__(self, db_path: str = _DEFAULT_DB):
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS url_queue (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    domain_id   TEXT NOT NULL,
                    url         TEXT NOT NULL,
                    priority    INTEGER DEFAULT 0,
                    added_at    TEXT DEFAULT (datetime('now')),
                    processed_at TEXT,
                    status      TEXT DEFAULT 'pending',
                    UNIQUE(domain_id, url)
                )
            """)

    def enqueue(self, domain_id: str, url: str, priority: int = 0) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR IGNORE INTO url_queue (domain_id, url, priority) VALUES (?,?,?)",
                (domain_id, url, priority),
            )

    def dequeue(self, domain_id: str, limit: int = 10) -> list[str]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT url FROM url_queue WHERE domain_id=? AND status='pending' "
                "ORDER BY priority DESC, id LIMIT ?",
                (domain_id, limit),
            ).fetchall()
            urls = [r[0] for r in rows]
            if urls:
                placeholders = ",".join("?" * len(urls))
                conn.execute(
                    f"UPDATE url_queue SET status='processing' "
                    f"WHERE domain_id=? AND url IN ({placeholders})",
                    [domain_id] + urls,
                )
        return urls

    def mark_done(self, domain_id: str, url: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE url_queue SET status='done', processed_at=datetime('now') "
                "WHERE domain_id=? AND url=?",
                (domain_id, url),
            )

    def has_pending(self, domain_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM url_queue WHERE domain_id=? AND status='pending' LIMIT 1",
                (domain_id,),
            ).fetchone()
        return row is not None

    def pending_count(self, domain_id: str) -> int:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM url_queue WHERE domain_id=? AND status='pending'",
                (domain_id,),
            ).fetchone()
        return row[0] if row else 0

    def reset_processing(self, domain_id: str) -> None:
        """Reset 'processing' entries back to 'pending' to recover from crashes."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE url_queue SET status='pending' WHERE domain_id=? AND status='processing'",
                (domain_id,),
            )

    def clear(self, domain_id: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM url_queue WHERE domain_id=?", (domain_id,))
