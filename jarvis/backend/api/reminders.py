"""Reminders CRUD API endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from backend.database.connection import get_db
from backend.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ReminderCreate(BaseModel):
    """Fields required to create a new reminder."""

    title: str
    message: str | None = None
    remind_at: str  # ISO datetime string e.g. "2024-12-31 08:00"


class ReminderUpdate(BaseModel):
    """Fields that can be updated on an existing reminder.  All are optional."""

    title: str | None = None
    message: str | None = None
    remind_at: str | None = None
    is_triggered: bool | None = None


class ReminderResponse(BaseModel):
    """Full reminder representation returned by the API."""

    id: int
    title: str
    message: str | None
    remind_at: str
    is_triggered: bool
    created_at: str


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _row_to_reminder(row: Any) -> ReminderResponse:
    """Convert an aiosqlite Row to a :class:`ReminderResponse`.

    Args:
        row: An aiosqlite Row from the reminders table.

    Returns:
        :class:`ReminderResponse` instance.
    """
    return ReminderResponse(
        id=row["id"],
        title=row["title"],
        message=row["message"],
        remind_at=row["remind_at"],
        is_triggered=bool(row["is_triggered"]),
        created_at=row["created_at"],
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[ReminderResponse], summary="List all reminders")
async def list_reminders() -> list[ReminderResponse]:
    """Return all reminders ordered by scheduled time.

    Returns:
        List of :class:`ReminderResponse` objects.
    """
    async for db in get_db():
        async with db.execute("SELECT * FROM reminders ORDER BY remind_at ASC") as cursor:
            rows = await cursor.fetchall()
    return [_row_to_reminder(r) for r in rows]


@router.post("/", response_model=ReminderResponse, status_code=201, summary="Create a reminder")
async def create_reminder(reminder: ReminderCreate) -> ReminderResponse:
    """Create a new reminder and return the persisted record.

    Args:
        reminder: Reminder creation payload.

    Returns:
        Newly created :class:`ReminderResponse`.
    """
    async for db in get_db():
        cursor = await db.execute(
            "INSERT INTO reminders (title, message, remind_at) VALUES (?, ?, ?)",
            (reminder.title, reminder.message, reminder.remind_at),
        )
        await db.commit()
        reminder_id = cursor.lastrowid
        async with db.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,)) as c:
            row = await c.fetchone()

    if row is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve created reminder.")
    return _row_to_reminder(row)


@router.put("/{reminder_id}", response_model=ReminderResponse, summary="Update a reminder")
async def update_reminder(reminder_id: int, updates: ReminderUpdate) -> ReminderResponse:
    """Partially update an existing reminder.

    Args:
        reminder_id: Primary key of the reminder to update.
        updates: Fields to update (``None`` values are ignored).

    Returns:
        Updated :class:`ReminderResponse`.
    """
    raw = updates.model_dump()
    fields: dict[str, Any] = {}
    for k, v in raw.items():
        if v is not None:
            fields[k] = int(v) if k == "is_triggered" else v

    if not fields:
        raise HTTPException(status_code=400, detail="No fields provided for update.")

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [reminder_id]

    async for db in get_db():
        cursor = await db.execute(
            f"UPDATE reminders SET {set_clause} WHERE id = ?", values  # noqa: S608
        )
        await db.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Reminder {reminder_id} not found.")
        async with db.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,)) as c:
            row = await c.fetchone()

    return _row_to_reminder(row)


@router.delete("/{reminder_id}", status_code=204, summary="Delete a reminder")
async def delete_reminder(reminder_id: int) -> Response:
    """Delete a reminder by ID.

    Args:
        reminder_id: Primary key of the reminder to delete.
    """
    async for db in get_db():
        cursor = await db.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
        await db.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Reminder {reminder_id} not found.")
    return Response(status_code=204)
