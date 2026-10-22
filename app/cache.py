"""SQLite cache for generated content, keyed by (topic_id, model, kind).

`kind` distinguishes different generated artifacts for the same topic --
"explain" and "reading_list" -- without needing separate tables.
"""
import json
import os
import sqlite3
from pathlib import Path

# Vercel's filesystem is read-only except /tmp, and /tmp doesn't persist
# across invocations -- caching is best-effort there (see README). On a
# normal host (Railway etc.) this just lives in data/cache.db as usual.
DB_PATH = (
    Path("/tmp/cache.db") if os.environ.get("VERCEL")
    else Path(__file__).resolve().parent.parent / "data" / "cache.db"
)


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS generated (
            topic_id TEXT NOT NULL,
            model TEXT NOT NULL,
            kind TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (topic_id, model, kind)
        )
        """
    )
    return conn


def get(topic_id: str, model: str, kind: str) -> dict | None:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT payload FROM generated WHERE topic_id = ? AND model = ? AND kind = ?",
            (topic_id, model, kind),
        ).fetchone()
        return json.loads(row[0]) if row else None
    finally:
        conn.close()


def put(topic_id: str, model: str, kind: str, payload: dict) -> None:
    conn = _connect()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO generated (topic_id, model, kind, payload) VALUES (?, ?, ?, ?)",
            (topic_id, model, kind, json.dumps(payload, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        conn.close()
