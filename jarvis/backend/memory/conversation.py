"""Conversation history persistence — load from / save to SQLite."""

from backend.database.connection import get_db
from backend.utils.logger import get_logger

logger = get_logger(__name__)


async def load_history(session_id: str, limit: int = 20) -> list[dict[str, str]]:
    """Load the most recent *limit* messages for *session_id* from the database.

    Args:
        session_id: The unique session identifier.
        limit: Maximum number of messages to return (default 20).

    Returns:
        A list of ``{role, content}`` dicts ordered oldest-first, suitable for
        passing to the Gemini message adapter.
    """
    async for db in get_db():
        async with db.execute(
            """
            SELECT role, content FROM conversations
            WHERE session_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (session_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()

    # Rows are newest-first; reverse to get chronological order
    return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]


async def save_message(session_id: str, role: str, content: str) -> None:
    """Persist a single chat message to the conversations table.

    Args:
        session_id: The unique session identifier.
        role: Chat role string - ``'user'``, ``'assistant'``, or ``'system'``.
        content: The message text.
    """
    async for db in get_db():
        await db.execute(
            """
            INSERT INTO conversations (session_id, role, content)
            VALUES (?, ?, ?)
            """,
            (session_id, role, content),
        )
        await db.commit()
    logger.debug("Saved %s message for session %s", role, session_id)
