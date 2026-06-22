"""Async SQLite connection management using aiosqlite."""

from collections.abc import AsyncGenerator
from typing import Any

import aiosqlite

from backend.config import settings
from backend.database.models import ALL_TABLES
from backend.utils.logger import get_logger

logger = get_logger(__name__)


async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """Yield an aiosqlite connection and close it when done.

    Usage:
        async with get_db() as db:
            await db.execute(...)
    """
    async with aiosqlite.connect(settings.database_url) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA foreign_keys=ON;")
        yield db


async def init_db() -> None:
    """Create all application tables if they do not already exist."""
    logger.info("Initialising database at '%s'", settings.database_url)
    async with aiosqlite.connect(settings.database_url) as db:
        await db.execute("PRAGMA journal_mode=WAL;")
        await db.execute("PRAGMA foreign_keys=ON;")
        for statement in ALL_TABLES:
            await db.execute(statement)
        await db.commit()
    logger.info("Database initialisation complete.")
