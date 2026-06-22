"""WebSocket connection manager and chat / voice-state routes.

Two WebSocket endpoints are exposed:
  /ws/chat         — bidirectional streaming AI chat (existing)
  /ws/voice-state  — read-only broadcast channel; the voice assistant
                     process pushes state changes via REST and the manager
                     fans them out to every connected browser tab.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.ai.chat_engine import chat_engine
from backend.commands.dispatcher import dispatch
from backend.utils.helpers import generate_session_id
from backend.utils.logger import get_logger

logger = get_logger(__name__)

ws_router = APIRouter()


class ConnectionManager:
    """Manages all active WebSocket connections and supports broadcast messaging.

    A single global instance (``manager``) is used throughout the application.
    """

    def __init__(self) -> None:
        """Initialise the empty connection pools."""
        # Chat clients (bidirectional)
        self.active_connections: list[WebSocket] = []
        # Voice-state clients (receive-only broadcasts)
        self.voice_state_connections: list[WebSocket] = []
        # Last known voice state — returned to clients that connect late
        self.current_voice_state: str = "idle"

    # ------------------------------------------------------------------
    # Chat connections
    # ------------------------------------------------------------------

    async def connect(self, websocket: WebSocket) -> None:
        """Accept the WebSocket handshake and register the chat connection.

        Args:
            websocket: Incoming WebSocket connection from FastAPI.
        """
        await websocket.accept()
        self.active_connections.append(websocket)
        client = websocket.client
        client_addr = f"{client.host}:{client.port}" if client else "unknown"
        logger.info(
            "WebSocket connected from %s on /ws/chat. Total: %d",
            client_addr,
            len(self.active_connections),
        )

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a chat WebSocket from the active connections list.

        Args:
            websocket: The WebSocket connection to remove.
        """
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        client = websocket.client
        client_addr = f"{client.host}:{client.port}" if client else "unknown"
        logger.info(
            "WebSocket disconnected from %s. Total: %d",
            client_addr,
            len(self.active_connections),
        )

    async def send_personal(self, message: str, websocket: WebSocket) -> None:
        """Send a text message to a single WebSocket client.

        Args:
            message: The message string to send.
            websocket: Target WebSocket connection.
        """
        await websocket.send_text(message)
        preview = message[:120] + ("…" if len(message) > 120 else "")
        logger.info("WebSocket message sent: %s", preview)

    async def broadcast(self, message: str) -> None:
        """Broadcast a message to all active chat WebSocket connections.

        Dead connections are silently removed from the pool.

        Args:
            message: The message string to broadcast.
        """
        dead: list[WebSocket] = []
        for connection in list(self.active_connections):
            try:
                await connection.send_text(message)
            except Exception:  # pylint: disable=broad-except
                dead.append(connection)
        for ws in dead:
            self.disconnect(ws)

    # ------------------------------------------------------------------
    # Voice-state connections
    # ------------------------------------------------------------------

    async def connect_voice_state(self, websocket: WebSocket) -> None:
        """Accept a voice-state WebSocket and register it.

        Immediately sends the current voice state so the client
        doesn't have to wait for the next state change.

        Args:
            websocket: Incoming WebSocket for /ws/voice-state.
        """
        await websocket.accept()
        self.voice_state_connections.append(websocket)
        client = websocket.client
        client_addr = f"{client.host}:{client.port}" if client else "unknown"
        logger.info(
            "Voice-state WebSocket connected from %s. Total: %d",
            client_addr,
            len(self.voice_state_connections),
        )
        # Send current state immediately on connect
        try:
            await websocket.send_text(
                json.dumps(
                    {"type": "voice_state", "state": self.current_voice_state, "text": ""}
                )
            )
        except Exception:  # pylint: disable=broad-except
            pass

    def disconnect_voice_state(self, websocket: WebSocket) -> None:
        """Remove a voice-state WebSocket.

        Args:
            websocket: The WebSocket to remove.
        """
        if websocket in self.voice_state_connections:
            self.voice_state_connections.remove(websocket)
        client = websocket.client
        client_addr = f"{client.host}:{client.port}" if client else "unknown"
        logger.info(
            "Voice-state WebSocket disconnected from %s. Total: %d",
            client_addr,
            len(self.voice_state_connections),
        )

    async def broadcast_voice_state(self, message: str) -> None:
        """Broadcast a voice state message to all voice-state clients.

        Dead connections are silently removed.

        Args:
            message: JSON string to broadcast.
        """
        dead: list[WebSocket] = []
        for connection in list(self.voice_state_connections):
            try:
                await connection.send_text(message)
            except Exception:  # pylint: disable=broad-except
                dead.append(connection)
        for ws in dead:
            self.disconnect_voice_state(ws)


# Global singleton
manager = ConnectionManager()


# ---------------------------------------------------------------------------
# /ws/chat — bidirectional streaming AI chat
# ---------------------------------------------------------------------------

@ws_router.websocket("/chat")
async def websocket_chat_endpoint(websocket: WebSocket) -> None:
    """Handle bidirectional chat over WebSocket.

    Incoming JSON: ``{"message": "...", "session_id": "..."}``
    Outgoing JSON chunks: ``{"type": "chunk"|"done"|"error", "content": "..."}``

    The endpoint tries command dispatching first; if no command matches it
    streams the AI response back to the client.
    """
    await manager.connect(websocket)
    session_id = generate_session_id()

    try:
        while True:
            raw = await websocket.receive_text()
            logger.info(
                "WebSocket message received: %s",
                raw[:200] + ("…" if len(raw) > 200 else ""),
            )
            try:
                data: dict[str, Any] = json.loads(raw)
            except json.JSONDecodeError:
                await manager.send_personal(
                    json.dumps({"type": "error", "content": "Invalid JSON payload."}),
                    websocket,
                )
                continue

            user_message: str = data.get("message", "").strip()
            session_id = data.get("session_id", session_id)
            file_path = data.get("file_path")

            if not user_message:
                continue

            # Try command dispatcher first
            command_result = await dispatch(user_message, session_id)
            if command_result is not None:
                await manager.send_personal(
                    json.dumps({"type": "chunk", "content": command_result}),
                    websocket,
                )
                await manager.send_personal(
                    json.dumps({"type": "done", "content": ""}),
                    websocket,
                )
                continue

            # Fall through to streaming AI response
            try:
                async for chunk in chat_engine.stream_chat(
                    session_id, user_message, file_path=file_path
                ):
                    await manager.send_personal(
                        json.dumps({"type": "chunk", "content": chunk}),
                        websocket,
                    )
                await manager.send_personal(
                    json.dumps({"type": "done", "content": ""}),
                    websocket,
                )
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("WebSocket AI error: %s", exc)
                await manager.send_personal(
                    json.dumps({"type": "error", "content": str(exc)}),
                    websocket,
                )

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected from /ws/chat")
        manager.disconnect(websocket)
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Unexpected WebSocket error: %s", exc)
        manager.disconnect(websocket)


# ---------------------------------------------------------------------------
# /ws/voice-state — one-way broadcast for orb animation
# ---------------------------------------------------------------------------

@ws_router.websocket("/voice-state")
async def websocket_voice_state_endpoint(websocket: WebSocket) -> None:
    """Receive-only WebSocket for voice assistant state broadcasts.

    The frontend connects here to receive real-time voice state updates
    (idle / listening / processing / speaking / error) that drive the
    orb animation.  The channel is one-way: the browser never sends on it.
    """
    await manager.connect_voice_state(websocket)

    try:
        # Keep alive — we only send, never receive meaningful data.
        # ``receive_text()`` will raise WebSocketDisconnect when the browser
        # closes the tab or navigates away.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        logger.info("Voice-state WebSocket client disconnected.")
        manager.disconnect_voice_state(websocket)
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Unexpected voice-state WebSocket error: %s", exc)
        manager.disconnect_voice_state(websocket)
