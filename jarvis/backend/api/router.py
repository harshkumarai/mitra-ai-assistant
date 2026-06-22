"""Main API router: aggregates all sub-routers under /api/v1."""

from fastapi import APIRouter

from backend.api import chat, files, memory, notes, reminders, system, tasks, speech, voice
from backend.websocket.manager import ws_router

# Primary REST API router
api_router = APIRouter()

api_router.include_router(chat.router,      prefix="/chat",      tags=["Chat"])
api_router.include_router(tasks.router,     prefix="/tasks",     tags=["Tasks"])
api_router.include_router(notes.router,     prefix="/notes",     tags=["Notes"])
api_router.include_router(reminders.router, prefix="/reminders", tags=["Reminders"])
api_router.include_router(system.router,    prefix="/system",    tags=["System"])
api_router.include_router(files.router,     prefix="/files",     tags=["Files"])
api_router.include_router(speech.router,    prefix="/speech",    tags=["Speech"])
api_router.include_router(memory.router,    prefix="/memory",    tags=["Memory"])
api_router.include_router(voice.router,     prefix="/voice",     tags=["Voice"])

# WebSocket router (mounted separately at /ws by main.py)
__all__ = ["api_router", "ws_router"]
