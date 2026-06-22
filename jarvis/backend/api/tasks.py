"""Tasks CRUD API endpoints."""

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

class TaskCreate(BaseModel):
    """Fields required to create a new task."""

    title: str
    description: str | None = None
    due_date: str | None = None
    priority: str = "medium"
    status: str = "pending"


class TaskUpdate(BaseModel):
    """Fields that can be updated on an existing task.  All are optional."""

    title: str | None = None
    description: str | None = None
    due_date: str | None = None
    priority: str | None = None
    status: str | None = None


class TaskResponse(BaseModel):
    """Full task representation returned by the API."""

    id: int
    title: str
    description: str | None
    due_date: str | None
    priority: str
    status: str
    created_at: str
    updated_at: str


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _row_to_task(row: Any) -> TaskResponse:
    """Convert an aiosqlite Row to a :class:`TaskResponse`.

    Args:
        row: An aiosqlite Row from the tasks table.

    Returns:
        :class:`TaskResponse` instance.
    """
    return TaskResponse(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        due_date=row["due_date"],
        priority=row["priority"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[TaskResponse], summary="List all tasks")
async def list_tasks(status: str | None = None) -> list[TaskResponse]:
    """Return all tasks, optionally filtered by *status*.

    Args:
        status: Optional status filter (``'pending'``, ``'done'``, etc.).

    Returns:
        List of :class:`TaskResponse` objects.
    """
    async for db in get_db():
        if status:
            async with db.execute(
                "SELECT * FROM tasks WHERE status = ? ORDER BY id DESC", (status,)
            ) as cursor:
                rows = await cursor.fetchall()
        else:
            async with db.execute("SELECT * FROM tasks ORDER BY id DESC") as cursor:
                rows = await cursor.fetchall()
    return [_row_to_task(r) for r in rows]


@router.post("/", response_model=TaskResponse, status_code=201, summary="Create a task")
async def create_task(task: TaskCreate) -> TaskResponse:
    """Create a new task and return the persisted record.

    Args:
        task: Task creation payload.

    Returns:
        Newly created :class:`TaskResponse`.
    """
    async for db in get_db():
        cursor = await db.execute(
            """
            INSERT INTO tasks (title, description, due_date, priority, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            (task.title, task.description, task.due_date, task.priority, task.status),
        )
        await db.commit()
        task_id = cursor.lastrowid
        async with db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)) as c:
            row = await c.fetchone()

    if row is None:
        raise HTTPException(status_code=500, detail="Failed to retrieve created task.")
    return _row_to_task(row)


@router.put("/{task_id}", response_model=TaskResponse, summary="Update a task")
async def update_task(task_id: int, updates: TaskUpdate) -> TaskResponse:
    """Partially update an existing task.

    Args:
        task_id: Primary key of the task to update.
        updates: Fields to update (``None`` values are ignored).

    Returns:
        Updated :class:`TaskResponse`.
    """
    fields = {k: v for k, v in updates.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="No fields provided for update.")

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    set_clause += ", updated_at = datetime('now')"
    values = list(fields.values()) + [task_id]

    async for db in get_db():
        cursor = await db.execute(
            f"UPDATE tasks SET {set_clause} WHERE id = ?", values  # noqa: S608
        )
        await db.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")
        async with db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)) as c:
            row = await c.fetchone()

    return _row_to_task(row)


@router.delete("/{task_id}", status_code=204, summary="Delete a task")
async def delete_task(task_id: int) -> Response:
    """Delete a task by ID.

    Args:
        task_id: Primary key of the task to delete.
    """
    async for db in get_db():
        cursor = await db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        await db.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found.")
    return Response(status_code=204)
