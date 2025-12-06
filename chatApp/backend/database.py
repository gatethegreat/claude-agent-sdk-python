"""
Database models and setup for session management.
"""

import sqlite3
from datetime import datetime
from typing import Optional, List
import uuid
import json


class Database:
    """SQLite database manager for session storage."""

    def __init__(self, db_path: str = "chat_sessions.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                session_id TEXT UNIQUE NOT NULL,
                sdk_session_id TEXT,
                client_name TEXT,
                title TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                last_message_preview TEXT,
                message_count INTEGER DEFAULT 0
            )
        """)

        # Add sdk_session_id column if it doesn't exist (migration)
        try:
            cursor.execute("ALTER TABLE sessions ADD COLUMN sdk_session_id TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                type TEXT NOT NULL,
                content TEXT NOT NULL,
                tools_used TEXT,
                timestamp TIMESTAMP NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_session_id
            ON messages(session_id)
        """)

        conn.commit()
        conn.close()

    def create_session(
        self, session_id: str, title: str = "New Chat", client_name: str = None
    ) -> dict:
        """Create a new session."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        cursor.execute(
            """
            INSERT INTO sessions (id, session_id, sdk_session_id, client_name, title, created_at, updated_at, message_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (id, session_id, None, client_name, title, now, now, 0),
        )

        conn.commit()
        conn.close()

        return {
            "id": id,
            "session_id": session_id,
            "sdk_session_id": None,
            "client_name": client_name,
            "title": title,
            "created_at": now,
            "updated_at": now,
            "last_message_preview": None,
            "message_count": 0,
        }

    def get_session(self, id: str) -> Optional[dict]:
        """Get a session by ID."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM sessions WHERE id = ?", (id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

    def get_session_by_session_id(self, session_id: str) -> Optional[dict]:
        """Get a session by SDK session_id."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

    def get_session_by_sdk_session_id(self, sdk_session_id: str) -> Optional[dict]:
        """Get a session by Claude SDK session_id (the real one for resumption)."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM sessions WHERE sdk_session_id = ?", (sdk_session_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

    def list_sessions(self, limit: int = 50, client_name: str = None) -> List[dict]:
        """List all sessions ordered by updated_at desc, optionally filtered by client."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if client_name:
            cursor.execute(
                "SELECT * FROM sessions WHERE client_name = ? ORDER BY updated_at DESC LIMIT ?",
                (client_name, limit)
            )
        else:
            cursor.execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,)
            )
        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def update_session(
        self,
        id: str,
        title: Optional[str] = None,
        last_message_preview: Optional[str] = None,
        increment_message_count: bool = False,
        sdk_session_id: Optional[str] = None,
    ) -> bool:
        """Update a session."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        updates = ["updated_at = ?"]
        params = [datetime.now().isoformat()]

        if title is not None:
            updates.append("title = ?")
            params.append(title)

        if last_message_preview is not None:
            updates.append("last_message_preview = ?")
            params.append(last_message_preview)

        if increment_message_count:
            updates.append("message_count = message_count + 1")

        if sdk_session_id is not None:
            updates.append("sdk_session_id = ?")
            params.append(sdk_session_id)

        params.append(id)
        query = f"UPDATE sessions SET {', '.join(updates)} WHERE id = ?"

        cursor.execute(query, params)
        affected = cursor.rowcount
        conn.commit()
        conn.close()

        return affected > 0

    def delete_session(self, id: str) -> bool:
        """Delete a session and its messages."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Delete messages first
        cursor.execute("DELETE FROM messages WHERE session_id = ?", (id,))

        # Delete session
        cursor.execute("DELETE FROM sessions WHERE id = ?", (id,))
        affected = cursor.rowcount
        conn.commit()
        conn.close()

        return affected > 0

    def store_message(
        self,
        session_id: str,
        type: str,
        content: str,
        tools_used: Optional[List[dict]] = None,
        timestamp: Optional[str] = None,
    ) -> dict:
        """Store a message for a session."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        id = str(uuid.uuid4())
        timestamp = timestamp or datetime.now().isoformat()
        tools_json = json.dumps(tools_used) if tools_used else None

        cursor.execute(
            """
            INSERT INTO messages (id, session_id, type, content, tools_used, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (id, session_id, type, content, tools_json, timestamp),
        )

        conn.commit()
        conn.close()

        return {
            "id": id,
            "session_id": session_id,
            "type": type,
            "content": content,
            "tools_used": tools_used,
            "timestamp": timestamp,
        }

    def get_messages(self, session_id: str) -> List[dict]:
        """Get all messages for a session ordered by timestamp."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp ASC",
            (session_id,),
        )
        rows = cursor.fetchall()
        conn.close()

        messages = []
        for row in rows:
            msg = dict(row)
            # Parse tools_used JSON
            if msg["tools_used"]:
                msg["tools_used"] = json.loads(msg["tools_used"])
            messages.append(msg)

        return messages


# Global database instance - use /app/data for Docker volume persistence
import os
db_path = os.environ.get("DATABASE_PATH", "/app/data/chat_sessions.db")
db = Database(db_path)
