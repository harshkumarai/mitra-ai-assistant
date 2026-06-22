"""Notes CRUD API endpoints."""

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

class NoteCreate(BaseModel):
    """Fields required to create a new note."""

    title: str
    content: str | None = None
    tags: str | None = None


class NoteUpdate(BaseModel):
    """Fields that can be updated on an existing note.  All are optional."""

    title: str | None = None
    content: str | None = None
    tags: str | None = None


class NoteResponse(BaseModel):
    """Full note representation returned by the API."""

    id: int
    title: str
    content: str | None
    tags: str | None
    created_at: str
    updated_at: str


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _row_to_note(row: Any) -> NoteResponse:
    """Convert an aiosqlite Row to a :class:`NoteResponse`.

    Args:
        row: An aiosqlite Row from the notes table.

    Returns:
        :class:`NoteResponse` instance.
    """
    return NoteResponse(
        id=row["id"],
        title=row["title"],
        content=row["content"],
        tags=row["tags"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[NoteResponse], summary="List all notes")
async def list_notes() -> list[NoteResponse]:
    """Return all notes ordered by most recently created.

    Returns:
        List of :class:`NoteResponse` objects.
    """
    async for db in get_db():
        async with db.execute("SELECT * FROM notes ORDER BY id DESC") as cursor:
            rows = await cursor.fetchall()
    return [_row_to_note(r) for r in rows]


@router.post("/", response_model=NoteResponse, status_code=201, summary="Create a note")
async def create_note(note: NoteCreate) -> NoteResponse:
    """Create a new note and return the persisted record.

    Args:
        note: Note creation payload.

    Returns:
        Newly created :class:`NoteResponse`.
    """
    async for db in get_db():
        cursor = await db.execute(
            "INSERT INTO notes (title, content, tags) VALUES (?, ?, ?)",
            (note.title, note.content, note.tags),
        )
        await db.commit()
        note_id = cursor.lastrowid
        async with db.execute("SELECT * FROM notes WHERE id = ?", (note_id,)) as c:
            row = await c.fetchone()

    if row is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve created note.")
    return _row_to_note(row)


@router.put("/{note_id}", response_model=NoteResponse, summary="Update a note")
async def update_note(note_id: int, updates: NoteUpdate) -> NoteResponse:
    """Partially update an existing note.

    Args:
        note_id: Primary key of the note to update.
        updates: Fields to update (``None`` values are ignored).

    Returns:
        Updated :class:`NoteResponse`.
    """
    fields = {k: v for k, v in updates.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="No fields provided for update.")

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    set_clause += ", updated_at = datetime('now')"
    values = list(fields.values()) + [note_id]

    async for db in get_db():
        cursor = await db.execute(
            f"UPDATE notes SET {set_clause} WHERE id = ?", values  # noqa: S608
        )
        await db.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Note {note_id} not found.")
        async with db.execute("SELECT * FROM notes WHERE id = ?", (note_id,)) as c:
            row = await c.fetchone()

    return _row_to_note(row)


@router.delete("/{note_id}", status_code=204, summary="Delete a note")
async def delete_note(note_id: int) -> Response:
    """Delete a note by ID.

    Args:
        note_id: Primary key of the note to delete.
    """
    async for db in get_db():
        cursor = await db.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        await db.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Note {note_id} not found.")
    return Response(status_code=204)
