"""
Private, per-session memory.

This store holds the raw conversation transcript and anything specific to
*this* person / *this* session. It is never read by another session or
agent, and it is never written directly into the shared knowledge base --
only distilled, generalized knowledge extracted from it (see extractor.py)
is allowed to cross that boundary.
"""
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from config import PRIVATE_DB_PATH


class PrivateMemoryStore:
    def __init__(self, db_path: str = PRIVATE_DB_PATH):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    consolidated INTEGER DEFAULT 0
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
                """
            )

    # -- session lifecycle ---------------------------------------------
    def create_session(self, agent_id: str) -> str:
        session_id = str(uuid.uuid4())
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sessions (session_id, agent_id, created_at) VALUES (?, ?, ?)",
                (session_id, agent_id, time.time()),
            )
        return session_id

    def delete_session(self, session_id: str):
        """Purge a session's private memory entirely."""
        with self._connect() as conn:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))

    def mark_consolidated(self, session_id: str):
        with self._connect() as conn:
            conn.execute(
                "UPDATE sessions SET consolidated = 1 WHERE session_id = ?", (session_id,)
            )

    def list_sessions(self, agent_id: Optional[str] = None) -> List[Dict]:
        with self._connect() as conn:
            if agent_id:
                rows = conn.execute(
                    "SELECT * FROM sessions WHERE agent_id = ? ORDER BY created_at DESC",
                    (agent_id,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM sessions ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    # -- messages ---------------------------------------------------------
    def add_message(self, session_id: str, role: str, content: str):
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (session_id, role, content, time.time()),
            )

    def get_messages(self, session_id: str) -> List[Dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
        return [dict(r) for r in rows]
