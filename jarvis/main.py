"""MITRA FastAPI application entry point."""

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

# Keep the existing backend.* imports working whether the app is started from
# the repository root (`uvicorn jarvis.main:app`) or from inside `jarvis/`.
JARVIS_DIR = Path(__file__).resolve().parent
if str(JARVIS_DIR) not in sys.path:
    sys.path.insert(0, str(JARVIS_DIR))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.api.router import api_router, ws_router
from backend.config import settings
from backend.database.connection import init_db
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    """Manage application startup and shutdown.

    On startup:
    - Initialises the SQLite database (creates tables if absent).

    On shutdown:
    - Logs a clean exit message.
    """
    logger.info("MITRA starting up…")
    await init_db()
    logger.info("MITRA is online and ready to assist. Listening on %s:%d", settings.jarvis_host, settings.jarvis_port)
    yield
    logger.info("MITRA shutting down.")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    Returns:
        Configured :class:`FastAPI` instance.
    """
    app = FastAPI(
        title="MITRA",
        description="MITRA — your personal AI assistant with voice, memory, and productivity tools.",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS — allow all origins for local development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Static files (frontend)
    frontend_dir = Path(__file__).parent / "frontend"
    dist_dir = frontend_dir / "dist"
    if dist_dir.exists():
        frontend_dir = dist_dir

    if frontend_dir.exists():
        app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

    # REST API at /api/v1
    app.include_router(api_router, prefix="/api/v1")

    # WebSocket at /ws
    app.include_router(ws_router, prefix="/ws")

    # Root route — serve index.html if present, else health JSON
    @app.get("/", include_in_schema=False)
    async def serve_index() -> Any:
        """Serve the frontend index.html or a health-check response.

        Returns:
            :class:`FileResponse` for index.html or a JSON health-check dict.
        """
        index_path = frontend_dir / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return JSONResponse(
            {"status": "online", "name": "MITRA", "version": "1.0.0"},
            status_code=200,
        )

    @app.get("/health", tags=["Health"])
    async def health_check() -> dict[str, str]:
        """Simple health-check endpoint.

        Returns:
            Dict with ``status``.
        """
        return {"status": "ok"}

    return app


# ---------------------------------------------------------------------------
# Application instance
# ---------------------------------------------------------------------------

app = create_app()

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=settings.jarvis_host,
        port=settings.jarvis_port,
        log_level=settings.log_level.lower(),
    )
