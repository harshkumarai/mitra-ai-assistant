"""Conversation engine: wraps Gemini calls with memory and streaming support."""

from __future__ import annotations

import base64
import mimetypes
import os
import re
from collections.abc import AsyncGenerator
from typing import Any

from backend.ai.client import ai_client
from backend.ai.prompts import get_system_prompt
from backend.memory.conversation import load_history, save_message
from backend.utils.logger import get_logger
from backend.utils.parsers import parse_document

logger = get_logger(__name__)

# Use Gemini Flash as the default multimodal model
_DEFAULT_MODEL = "gemini-3.1-flash-lite"
_DEFAULT_MAX_TOKENS = 2048  # bump max tokens for longer file/code responses

# Regex patterns to detect the user telling us their name or a fact to remember
_NAME_PATTERN    = re.compile(
    r"\b(?:my name is|i(?:'m| am) called|call me|i go by)\s+([A-Za-z][A-Za-z\s]{1,30})",
    re.IGNORECASE,
)
_REMEMBER_PATTERN = re.compile(
    r"\b(?:remember (?:that )?|note (?:that )?|keep in mind (?:that )?|save (?:that )?)(.{5,120})",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Memory helpers
# ---------------------------------------------------------------------------

async def _load_user_facts() -> dict[str, str]:
    """Load all user_preferences rows into a plain dict."""
    try:
        from backend.database.connection import get_db
        async for db in get_db():
            async with db.execute(
                "SELECT key, value FROM user_preferences"
            ) as cursor:
                rows = await cursor.fetchall()
        return {row["key"]: row["value"] for row in rows}
    except Exception as exc:
        logger.warning("Could not load user facts: %s", exc)
        return {}


async def _maybe_save_user_fact(user_message: str) -> None:
    """Detect name / remember declarations and persist them."""
    try:
        from backend.database.connection import get_db

        m = _NAME_PATTERN.search(user_message)
        if m:
            name = m.group(1).strip().split()[0].capitalize()  # first word only
            async for db in get_db():
                await db.execute(
                    """INSERT INTO user_preferences (key, value)
                       VALUES ('user_name', ?)
                       ON CONFLICT(key) DO UPDATE
                           SET value = excluded.value,
                               updated_at = datetime('now')""",
                    (name,),
                )
                await db.commit()
            logger.info("User name saved: %r", name)
            return

        m = _REMEMBER_PATTERN.search(user_message)
        if m:
            fact = m.group(1).strip()
            # Use first 3 words as a key
            key = "_".join(fact.lower().split()[:3]).replace("'", "")[:50]
            async for db in get_db():
                await db.execute(
                    """INSERT INTO user_preferences (key, value)
                       VALUES (?, ?)
                       ON CONFLICT(key) DO UPDATE
                           SET value = excluded.value,
                               updated_at = datetime('now')""",
                    (key, fact),
                )
                await db.commit()
            logger.info("User fact saved: %r = %r", key, fact)
    except Exception as exc:
        logger.warning("Could not save user fact: %s", exc)


# ---------------------------------------------------------------------------
# ChatEngine
# ---------------------------------------------------------------------------

class ChatEngine:
    """High-level chat interface with per-session memory.

    Each call to :meth:`chat` or :meth:`stream_chat` automatically:
    1. Loads conversation history for the session from the database.
    2. Loads user facts from ``user_preferences`` and injects them into the prompt.
    3. Prepends the MITRA system prompt.
    4. Calls the Gemini API (supporting text and multi-modal images).
    5. Persists both the user message and the assistant response to the database.
    6. Detects "my name is / remember that" declarations and saves them.
    """

    async def _build_messages(
        self,
        session_id: str,
        user_message: str,
        file_path: str | None = None,
        voice_mode: bool = False,
    ) -> list[dict[str, Any]]:
        """Construct the full messages list for the Gemini request.

        Args:
            session_id: Unique session identifier.
            user_message: The latest user input.
            file_path: Optional path to an uploaded document or image file.
            voice_mode: When True, instructs the model to reply concisely for TTS.

        Returns:
            List of ``{role, content}`` dicts.
        """
        history      = await load_history(session_id, limit=20)
        user_facts   = await _load_user_facts()
        system_prompt = get_system_prompt(user_facts=user_facts, voice_mode=voice_mode)

        # Build user message content depending on attachment
        user_content: Any = user_message

        if file_path and os.path.exists(file_path):
            filename = os.path.basename(file_path)
            ext      = os.path.splitext(file_path.lower())[1]
            is_image = ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")

            if is_image:
                try:
                    with open(file_path, "rb") as image_file:
                        encoded = base64.b64encode(image_file.read()).decode("utf-8")
                    mime, _ = mimetypes.guess_type(file_path)
                    mime = mime or "image/jpeg"
                    image_url = f"data:{mime};base64,{encoded}"

                    user_content = [
                        {"type": "text", "text": user_message},
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url},
                        },
                    ]
                    logger.info("Vision model payload prepared for image: %s", filename)
                except Exception as exc:
                    logger.error("Failed to prepare image for vision request: %s", exc)
                    user_content = f"{user_message}\n\n[Failed to attach image: {filename}]"
            else:
                # Text-based file (PDF, DOCX, TXT)
                doc_text = parse_document(file_path)
                user_content = (
                    f"Context from attached file '{filename}':\n"
                    f"```\n{doc_text}\n```\n\n"
                    f"User Query: {user_message}"
                )
                logger.info("Document context injected for file: %s", filename)

        messages: list[dict[str, Any]] = [
            {"role": "system",  "content": system_prompt},
            *history,
            {"role": "user",    "content": user_content},
        ]
        return messages

    async def chat(
        self,
        session_id: str,
        user_message: str,
        file_path: str | None = None,
        model: str = _DEFAULT_MODEL,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
        voice_mode: bool = False,
    ) -> tuple[str, int]:
        """Send a message and return the full assistant reply.

        Args:
            session_id: Unique session identifier.
            user_message: The user's input text.
            file_path: Optional path to an uploaded file.
            model: Gemini model to use.
            max_tokens: Token budget for the completion.
            voice_mode: When True, prompt instructs model to reply concisely for TTS.

        Returns:
            Tuple of ``(response_text, tokens_used)``.  ``tokens_used`` is 0
            when the underlying API does not return usage data.

        Raises:
            RuntimeError: Propagated from :mod:`backend.ai.client` on API errors.
        """
        logger.info("Processing chat request for session %s", session_id)

        # Persist user fact if detected *before* building messages so the
        # updated fact is included in the system prompt of this very reply.
        await _maybe_save_user_fact(user_message)

        messages = await self._build_messages(
            session_id, user_message, file_path, voice_mode=voice_mode
        )

        try:
            logger.debug("Calling ai_client.complete for non-streaming chat")
            result        = await ai_client.complete(messages=messages, model=model, max_tokens=max_tokens)
            response_text = str(result)
            logger.info("Chat response generated successfully for session %s", session_id)
        except RuntimeError as exc:
            response_text = f"[MITRA Error] {exc}"
            logger.error("Chat engine error for session %s: %s", session_id, exc)
        except Exception as exc:
            response_text = f"[MITRA Error] Unexpected error: {exc}"
            logger.error("Unexpected error in chat for session %s: %s", session_id, exc)

        save_user_msg = user_message
        if file_path:
            save_user_msg += f" [Attached File: {os.path.basename(file_path)}]"

        await save_message(session_id, "user",      save_user_msg)
        await save_message(session_id, "assistant", response_text)

        return response_text, 0  # token count not surfaced by the helper

    async def stream_chat(
        self,
        session_id: str,
        user_message: str,
        file_path: str | None = None,
        model: str = _DEFAULT_MODEL,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
        voice_mode: bool = False,
    ) -> AsyncGenerator[str, None]:
        """Stream assistant reply chunks for a user message.

        Args:
            session_id: Unique session identifier.
            user_message: The user's input text.
            file_path: Optional path to an uploaded file.
            model: Gemini model to use.
            max_tokens: Token budget for the completion.
            voice_mode: When True, prompt instructs model to reply concisely for TTS.

        Yields:
            String chunks as they arrive from the Gemini streaming API.
        """
        logger.info("Processing stream chat request for session %s", session_id)

        await _maybe_save_user_fact(user_message)

        messages      = await self._build_messages(session_id, user_message, file_path, voice_mode=voice_mode)
        full_response: list[str] = []

        save_user_msg = user_message
        if file_path:
            save_user_msg += f" [Attached File: {os.path.basename(file_path)}]"

        await save_message(session_id, "user", save_user_msg)

        try:
            generator = ai_client.complete_stream(messages=messages, model=model, max_tokens=max_tokens)
            async for chunk in generator:
                full_response.append(chunk)
                yield chunk
            logger.info("Stream chat completed successfully for session %s", session_id)
        except RuntimeError as exc:
            error_msg = f"[MITRA Error] {exc}"
            logger.error("Stream chat error for session %s: %s", session_id, exc)
            yield error_msg
            full_response.append(error_msg)
        except Exception as exc:
            error_msg = f"[MITRA Error] Unexpected error: {exc}"
            logger.error("Unexpected error in stream chat for session %s: %s", session_id, exc)
            yield error_msg
            full_response.append(error_msg)

        await save_message(session_id, "assistant", "".join(full_response))


# Module-level singleton
chat_engine = ChatEngine()
