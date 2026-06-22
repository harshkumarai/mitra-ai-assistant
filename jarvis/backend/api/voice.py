"""Voice state API — receives state updates from the voice assistant process
and broadcasts them to all connected frontend clients via WebSocket.

Endpoints
---------
POST /api/v1/voice/state  — voice_assistant.py posts here when state changes
GET  /api/v1/voice/state  — query current voice state (for reconnecting clients)
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class VoiceStateUpdate(BaseModel):
    """Payload sent by voice_assistant.py when state changes."""

    state: str  # idle | listening | wake_detected | processing | speaking | error
    text: str = ""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/state", summary="Receive voice state update and broadcast to frontend")
async def update_voice_state(update: VoiceStateUpdate) -> dict[str, str]:
    """Accept a state change from the standalone voice assistant process.

    Broadcasts the new state to every frontend client connected on
    ``/ws/voice-state`` so the orb animation updates in real time.

    Args:
        update: The new voice state and optional display text.

    Returns:
        Acknowledgement dict with ``status`` and ``state``.
    """
    import json

    from backend.websocket.manager import manager

    payload = json.dumps(
        {
            "type":  "voice_state",
            "state": update.state,
            "text":  update.text,
        }
    )
    await manager.broadcast_voice_state(payload)
    manager.current_voice_state = update.state

    logger.info(
        "Voice state → %s  %s",
        update.state,
        f"({update.text[:60]})" if update.text else "",
    )
    return {"status": "ok", "state": update.state}


@router.get("/state", summary="Get current voice assistant state")
async def get_voice_state() -> dict[str, str]:
    """Return the most recently broadcast voice state.

    Useful for clients that connect after the last state change.

    Returns:
        Dict with ``state`` key.
    """
    from backend.websocket.manager import manager

    return {"state": manager.current_voice_state}
