"""User memory / preferences API — remember facts about the user.

Endpoints
---------
GET    /api/v1/memory/       — list all stored key-value facts
POST   /api/v1/memory/       — upsert a fact  {key, value}
GET    /api/v1/memory/{key}  — fetch one fact by key
DELETE /api/v1/memory/{key}  — remove a fact

The underlying table (``user_preferences``) is created by
``backend.database.models`` at startup.
"""

from __future__ import annotations

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

class MemoryItem(BaseModel):
    """A single user fact."""

    key: str
    value: str


class MemoryResponse(BaseModel):
    """Returned fact with metadata."""

    key: str
    value: str
    updated_at: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get(
    "/",
    response_model=list[MemoryResponse],
    summary="List all stored user facts",
)
async def list_memory() -> list[MemoryResponse]:
    """Return all user facts ordered alphabetically by key.

    Returns:
        List of :class:`MemoryResponse` items.
    """
    async for db in get_db():
        async with db.execute(
            "SELECT key, value, updated_at FROM user_preferences ORDER BY key"
        ) as cursor:
            rows = await cursor.fetchall()
    return [
        MemoryResponse(key=r["key"], value=r["value"], updated_at=r["updated_at"] or "")
        for r in rows
    ]


@router.post(
    "/",
    response_model=MemoryResponse,
    status_code=200,
    summary="Set (upsert) a user fact",
)
async def set_memory(item: MemoryItem) -> MemoryResponse:
    """Insert or update a user fact.

    Args:
        item: Key-value pair to store.

    Returns:
        The stored :class:`MemoryResponse`.
    """
    async for db in get_db():
        await db.execute(
            """
            INSERT INTO user_preferences (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE
                SET value      = excluded.value,
                    updated_at = datetime('now')
            """,
            (item.key.strip().lower(), item.value.strip()),
        )
        await db.commit()
        async with db.execute(
            "SELECT key, value, updated_at FROM user_preferences WHERE key = ?",
            (item.key.strip().lower(),),
        ) as cursor:
            row = await cursor.fetchone()

    logger.info("Memory upsert: %s = %r", item.key, item.value)
    return MemoryResponse(
        key=row["key"], value=row["value"], updated_at=row["updated_at"] or ""
    )


@router.get(
    "/{key}",
    response_model=MemoryResponse,
    summary="Get a single user fact by key",
)
async def get_memory(key: str) -> MemoryResponse:
    """Fetch one fact by its key.

    Args:
        key: The fact identifier (case-insensitive).

    Returns:
        :class:`MemoryResponse` if found.

    Raises:
        HTTPException: 404 if the key does not exist.
    """
    async for db in get_db():
        async with db.execute(
            "SELECT key, value, updated_at FROM user_preferences WHERE key = ?",
            (key.strip().lower(),),
        ) as cursor:
            row = await cursor.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail=f"Memory key '{key}' not found.")
    return MemoryResponse(
        key=row["key"], value=row["value"], updated_at=row["updated_at"] or ""
    )


@router.delete(
    "/{key}",
    status_code=204,
    summary="Delete a user fact",
)
async def delete_memory(key: str) -> Response:
    """Remove a fact by key.

    Args:
        key: The fact identifier to delete.

    Raises:
        HTTPException: 404 if the key does not exist.
    """
    async for db in get_db():
        cursor = await db.execute(
            "DELETE FROM user_preferences WHERE key = ?",
            (key.strip().lower(),),
        )
        await db.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Memory key '{key}' not found.")
    logger.info("Memory deleted: %s", key)
    return Response(status_code=204)
