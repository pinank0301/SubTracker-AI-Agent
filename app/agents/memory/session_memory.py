import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
# pyrefly: ignore [missing-import]
import psycopg2
# pyrefly: ignore [missing-import]
import psycopg2.extras
# pyrefly: ignore [missing-import]
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

logger = logging.getLogger(__name__)

# Default connection string — overridden via Settings / env
DEFAULT_DATABASE_URL = "postgresql://postgres:root@localhost:5432/subtracker"


class PersistentSessionMemory:
    """
    Persistent PostgreSQL-backed conversation memory manager.
    Stores full message trails by user_id and session_id across server restarts.
    Provides sliding context windows and cross-session user context retrieval.
    """

    def __init__(self, database_url: str = DEFAULT_DATABASE_URL, max_history_per_session: int = 12):
        self.database_url = database_url
        self.max_history = max_history_per_session
        self._init_db()

    def _get_connection(self):
        """Creates and returns a new PostgreSQL connection with RealDictCursor factory."""
        conn = psycopg2.connect(self.database_url)
        return conn

    def _init_db(self) -> None:
        """Initialize the conversation_messages table in PostgreSQL if it doesn't exist."""
        try:
            conn = self._get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS conversation_messages (
                            id SERIAL PRIMARY KEY,
                            user_id TEXT NOT NULL,
                            session_id TEXT NOT NULL,
                            role TEXT NOT NULL,
                            content TEXT NOT NULL,
                            intent TEXT,
                            timestamp TEXT NOT NULL
                        )
                    """)
                    cursor.execute("""
                        CREATE INDEX IF NOT EXISTS idx_user_id ON conversation_messages(user_id)
                    """)
                    cursor.execute("""
                        CREATE INDEX IF NOT EXISTS idx_session_id ON conversation_messages(session_id)
                    """)
                conn.commit()
            finally:
                conn.close()
            logger.info("Initialized Persistent PostgreSQL Conversation Database: %s", self.database_url.split("@")[-1])
        except Exception as e:
            logger.error("Failed to initialize PostgreSQL conversation database: %s", e)

    def add_user_message(self, session_id: str, message: str, user_id: str = "default-user", intent: Optional[str] = None) -> None:
        self._append_message(user_id=user_id, session_id=session_id, role="user", content=message, intent=intent)

    def add_ai_message(self, session_id: str, message: str, user_id: str = "default-user", intent: Optional[str] = None) -> None:
        self._append_message(user_id=user_id, session_id=session_id, role="assistant", content=message, intent=intent)

    def add_system_message(self, session_id: str, message: str, user_id: str = "default-user") -> None:
        self._append_message(user_id=user_id, session_id=session_id, role="system", content=message)

    def _append_message(self, user_id: str, session_id: str, role: str, content: str, intent: Optional[str] = None) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            conn = self._get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO conversation_messages (user_id, session_id, role, content, intent, timestamp) VALUES (%s, %s, %s, %s, %s, %s)",
                        (user_id, session_id, role, content, intent, now_iso)
                    )
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            logger.error("Failed to persist conversation message: %s", e)

    def get_messages(self, session_id: str) -> List[BaseMessage]:
        """Returns message list for the session formatted for LangChain models."""
        try:
            conn = self._get_connection()
            try:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    cursor.execute(
                        "SELECT role, content FROM conversation_messages WHERE session_id = %s ORDER BY id DESC LIMIT %s",
                        (session_id, self.max_history)
                    )
                    rows = cursor.fetchall()
            finally:
                conn.close()

            messages: List[BaseMessage] = []
            for row in reversed(rows):
                role = row["role"]
                content = row["content"]
                if role == "user":
                    messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    messages.append(AIMessage(content=content))
                else:
                    messages.append(SystemMessage(content=content))
            return messages
        except Exception as e:
            logger.error("Failed to fetch session messages: %s", e)
            return []

    def get_history_summary(self, session_id: str) -> str:
        """Returns formatted string representation of recent turns for current session."""
        try:
            conn = self._get_connection()
            try:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    cursor.execute(
                        "SELECT role, content FROM conversation_messages WHERE session_id = %s ORDER BY id DESC LIMIT %s",
                        (session_id, self.max_history)
                    )
                    rows = cursor.fetchall()
            finally:
                conn.close()

            if not rows:
                return "No previous conversation history in this session."

            lines = []
            for r in reversed(rows):
                prefix = "User" if r["role"] == "user" else "Assistant" if r["role"] == "assistant" else "System"
                lines.append(f"{prefix}: {r['content']}")
            return "\n".join(lines)
        except Exception as e:
            logger.error("Failed to get history summary: %s", e)
            return "No previous conversation history."

    def get_cross_session_context(self, user_id: str, current_session_id: str, limit: int = 6) -> str:
        """
        Retrieves context from previous sessions for the same user so the agent knows user preferences,
        prior questions, or previously discussed subscriptions.
        """
        if not user_id or user_id == "default-user":
            return ""
        try:
            conn = self._get_connection()
            try:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    cursor.execute(
                        "SELECT role, content, timestamp FROM conversation_messages WHERE user_id = %s AND session_id != %s ORDER BY id DESC LIMIT %s",
                        (user_id, current_session_id, limit)
                    )
                    rows = cursor.fetchall()
            finally:
                conn.close()

            if not rows:
                return ""

            lines = ["Prior User Interactions (Past Sessions):"]
            for r in reversed(rows):
                prefix = "User" if r["role"] == "user" else "Assistant"
                lines.append(f"- [{r['timestamp'][:10]}] {prefix}: {r['content']}")
            return "\n".join(lines)
        except Exception as e:
            logger.error("Failed to get cross-session context: %s", e)
            return ""

    def get_user_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        """Returns list of all session summaries for a user."""
        try:
            conn = self._get_connection()
            try:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT session_id, COUNT(*) as message_count, MIN(timestamp) as started_at, MAX(timestamp) as last_activity
                        FROM conversation_messages
                        WHERE user_id = %s
                        GROUP BY session_id
                        ORDER BY last_activity DESC
                    """, (user_id,))
                    rows = cursor.fetchall()
            finally:
                conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error("Failed to get user sessions: %s", e)
            return []

    def get_session_full_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Returns the full chronological message log for a session."""
        try:
            conn = self._get_connection()
            try:
                with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                    cursor.execute(
                        "SELECT id, user_id, session_id, role, content, intent, timestamp FROM conversation_messages WHERE session_id = %s ORDER BY id ASC",
                        (session_id,)
                    )
                    rows = cursor.fetchall()
            finally:
                conn.close()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error("Failed to fetch full session history: %s", e)
            return []

    def clear_session(self, session_id: str) -> bool:
        try:
            conn = self._get_connection()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM conversation_messages WHERE session_id = %s", (session_id,))
                conn.commit()
            finally:
                conn.close()
            logger.info("Cleared persistent session history for: %s", session_id)
            return True
        except Exception as e:
            logger.error("Failed to clear session %s: %s", session_id, e)
            return False


_global_memory: Optional[PersistentSessionMemory] = None


def get_session_memory() -> PersistentSessionMemory:
    global _global_memory
    if _global_memory is None:
        try:
            from app.config import get_settings
            settings = get_settings()
            db_url = settings.DATABASE_URL
        except Exception:
            db_url = DEFAULT_DATABASE_URL
        _global_memory = PersistentSessionMemory(database_url=db_url)
    return _global_memory
