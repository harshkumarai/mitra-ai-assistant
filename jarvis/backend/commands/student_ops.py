"""Quick-add database helpers for student productivity commands."""

from backend.database.connection import get_db
from backend.utils.logger import get_logger

logger = get_logger(__name__)


async def add_task(title: str, due_date: str | None = None) -> str:
    """Create a new task record directly in the database.

    Args:
        title: Short task description.
        due_date: Optional ISO-format date string (``'YYYY-MM-DD'``).

    Returns:
        Confirmation message with the new task ID.
    """
    async for db in get_db():
        cursor = await db.execute(
            "INSERT INTO tasks (title, due_date, status) VALUES (?, ?, 'pending')",
            (title, due_date),
        )
        await db.commit()
        task_id = cursor.lastrowid
    logger.info("Quick-added task id=%s: %s", task_id, title)
    due_str = f" (due {due_date})" if due_date else ""
    return f"Task added: '{title}'{due_str}. ID: {task_id}."


async def add_note(title: str, content: str = "") -> str:
    """Create a new note record directly in the database.

    Args:
        title: Note title / heading.
        content: Optional note body text.

    Returns:
        Confirmation message with the new note ID.
    """
    async for db in get_db():
        cursor = await db.execute(
            "INSERT INTO notes (title, content) VALUES (?, ?)",
            (title, content),
        )
        await db.commit()
        note_id = cursor.lastrowid
    logger.info("Quick-added note id=%s: %s", note_id, title)
    return f"Note saved: '{title}'. ID: {note_id}."


async def add_reminder(title: str, remind_at: str) -> str:
    """Create a new reminder record directly in the database.

    Args:
        title: Short reminder label.
        remind_at: ISO-format datetime string (``'YYYY-MM-DD HH:MM'``).

    Returns:
        Confirmation message with the new reminder ID.
    """
    async for db in get_db():
        cursor = await db.execute(
            "INSERT INTO reminders (title, remind_at) VALUES (?, ?)",
            (title, remind_at),
        )
        await db.commit()
        reminder_id = cursor.lastrowid
    logger.info("Quick-added reminder id=%s: %s at %s", reminder_id, title, remind_at)
    return f"Reminder set: '{title}' at {remind_at}. ID: {reminder_id}."
