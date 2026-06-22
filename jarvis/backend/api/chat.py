"""Chat API endpoints: send messages and retrieve conversation history."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.ai.chat_engine import chat_engine
from backend.database.connection import get_db
from backend.utils.helpers import generate_session_id
from backend.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    """Request body for the POST /chat endpoint."""

    message: str
    session_id: str = ""
    file_path: str | None = None


class ChatResponse(BaseModel):
    """Response body returned by the POST /chat endpoint."""

    response: str
    session_id: str
    tokens_used: int


class MessageRecord(BaseModel):
    """A single conversation message as stored in the database."""

    id: int
    session_id: str
    role: str
    content: str
    timestamp: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/", response_model=ChatResponse, summary="Send a chat message")
async def send_message(request: ChatRequest) -> ChatResponse:
    """Send a message to MITRA and receive a reply.

    The engine checks the command dispatcher first; unmatched input is sent to
    the Gemini API. Conversation history is automatically persisted.

    Args:
        request: The chat request containing the message and optional session ID.

    Returns:
        :class:`ChatResponse` with the assistant reply.
    """
    session_id = request.session_id or generate_session_id()

    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    logger.info("Processing chat message for session %s: %s", session_id, request.message[:100])

    # Try command dispatch first
    try:
        from backend.commands.dispatcher import dispatch
        command_result = await dispatch(request.message, session_id)

        if command_result is not None:
            logger.info("Command dispatched successfully for session %s", session_id)
            return ChatResponse(
                response=command_result,
                session_id=session_id,
                tokens_used=0,
            )
    except Exception as exc:
        logger.error("Command dispatch error for session %s: %s", session_id, exc)
        # Continue to AI fallback

    # Fall through to AI
    try:
        response_text, tokens_used = await chat_engine.chat(
            session_id, request.message, file_path=request.file_path
        )
        logger.info("AI response generated for session %s, tokens used: %d", session_id, tokens_used)
    except RuntimeError as exc:
        logger.error("Chat engine error for session %s: %s", session_id, exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Unexpected error in chat for session %s: %s", session_id, exc)
        raise HTTPException(status_code=500, detail="An unexpected error occurred") from exc

    return ChatResponse(
        response=response_text,
        session_id=session_id,
        tokens_used=tokens_used,
    )


@router.get(
    "/history/{session_id}",
    response_model=list[MessageRecord],
    summary="Get conversation history",
)
async def get_history(session_id: str) -> list[MessageRecord]:
    """Return the last 50 messages for a given session.

    Args:
        session_id: The session whose history should be returned.

    Returns:
        List of :class:`MessageRecord` objects, oldest first.
    """
    rows: list[MessageRecord] = []
    try:
        async for db in get_db():
            async with db.execute(
                """
                SELECT id, session_id, role, content,
                       COALESCE(timestamp, datetime('now')) AS timestamp
                FROM conversations
                WHERE session_id = ?
                ORDER BY id DESC
                LIMIT 50
                """,
                (session_id,),
            ) as cursor:
                fetched = await cursor.fetchall()

        for row in reversed(fetched):
            rows.append(
                MessageRecord(
                    id=row["id"],
                    session_id=row["session_id"],
                    role=row["role"],
                    content=row["content"],
                    timestamp=row["timestamp"],
                )
            )
        logger.info("Retrieved %d messages for session %s", len(rows), session_id)
        return rows
    except Exception as exc:
        logger.error("Error retrieving history for session %s: %s", session_id, exc)
        raise HTTPException(status_code=500, detail="Failed to retrieve conversation history") from exc
