"""Async Gemini client wrapper with error handling."""

import base64
import io
import mimetypes
import wave
from collections.abc import AsyncGenerator
from typing import Any

from backend.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)

try:
    from google import genai
    from google.genai import types

    _gemini_available = True
except ImportError:
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]
    _gemini_available = False
    logger.warning("google-genai package not installed - AI features will be disabled.")


_DEFAULT_CHAT_MODEL = "gemini-3.1-flash-lite"
_DEFAULT_TTS_MODEL = "gemini-2.5-flash-preview-tts"
_DEFAULT_TRANSCRIPTION_PROMPT = (
    "Transcribe this audio exactly. Return only the spoken words, without commentary."
)

_VOICE_MAP = {
    "alloy": "Puck",
    "ash": "Charon",
    "ballad": "Orus",
    "coral": "Kore",
    "echo": "Fenrir",
    "fable": "Puck",
    "nova": "Kore",
    "onyx": "Charon",
    "sage": "Orus",
    "shimmer": "Kore",
}


class AIClient:
    """Thin async wrapper around the Google Gen AI SDK.

    The client is created lazily on first use so that a missing API key does
    not crash the server at startup.
    """

    _instance: "AIClient | None" = None

    def __init__(self) -> None:
        """Initialise the client; actual connection is deferred until first call."""
        self._client: Any = None

    def _get_client(self) -> Any:
        """Return and lazily create the underlying Gemini client."""
        if not _gemini_available:
            raise RuntimeError(
                "The 'google-genai' package is not installed. "
                "Run: pip install google-genai"
            )
        if not settings.gemini_api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. "
                "Add it to your .env file to enable AI features."
            )
        if self._client is None:
            self._client = genai.Client(api_key=settings.gemini_api_key)
        return self._client

    def _build_config(self, system_instruction: str | None, max_tokens: int) -> Any:
        config: dict[str, Any] = {"max_output_tokens": max_tokens}
        if system_instruction:
            config["system_instruction"] = system_instruction
        return types.GenerateContentConfig(**config)

    def _message_parts(self, content: Any) -> list[Any]:
        if isinstance(content, str):
            return [types.Part.from_text(text=content)]

        if not isinstance(content, list):
            return [types.Part.from_text(text=str(content))]

        parts: list[Any] = []
        for item in content:
            item_type = item.get("type") if isinstance(item, dict) else None
            if item_type == "text":
                parts.append(types.Part.from_text(text=item.get("text", "")))
            elif item_type == "image_url":
                image_url = item.get("image_url", {}).get("url", "")
                parts.append(self._image_part_from_data_url(image_url))
            else:
                parts.append(types.Part.from_text(text=str(item)))
        return [part for part in parts if part is not None]

    def _image_part_from_data_url(self, image_url: str) -> Any | None:
        if not image_url.startswith("data:") or ";base64," not in image_url:
            logger.warning("Skipping unsupported Gemini image payload.")
            return None

        header, encoded = image_url.split(";base64,", 1)
        mime_type = header.removeprefix("data:") or "image/jpeg"
        try:
            data = base64.b64decode(encoded)
        except ValueError as exc:
            logger.warning("Skipping invalid base64 image payload: %s", exc)
            return None
        return types.Part.from_bytes(data=data, mime_type=mime_type)

    def _to_gemini_contents(
        self, messages: list[dict[str, Any]]
    ) -> tuple[str | None, list[Any]]:
        system_instruction: str | None = None
        contents: list[Any] = []

        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")

            if role == "system":
                system_text = content if isinstance(content, str) else str(content)
                system_instruction = (
                    f"{system_instruction}\n\n{system_text}"
                    if system_instruction
                    else system_text
                )
                continue

            gemini_role = "model" if role == "assistant" else "user"
            parts = self._message_parts(content)
            if parts:
                contents.append(types.Content(role=gemini_role, parts=parts))

        return system_instruction, contents

    def _handle_gemini_error(self, exc: Exception, model: str | None = None) -> RuntimeError:
        message = str(exc)
        status_code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
        api_key_loaded = bool(settings.gemini_api_key)

        # Log detailed info requested by the user
        logger.error(
            "Gemini API Error Detail:\n"
            "  Model: %s\n"
            "  API Key Loaded Status: %s\n"
            "  Full Gemini Error Message: %s",
            model or "unknown",
            "Loaded" if api_key_loaded else "Not Loaded",
            message
        )

        if status_code in (401, 403) or "api key" in message.lower():
            logger.error("Gemini authentication failed: %s", exc)
            return RuntimeError(
                "Invalid Gemini API key. Please check your GEMINI_API_KEY setting."
            )

        if status_code == 429 or "quota" in message.lower() or "rate" in message.lower():
            logger.warning("Gemini rate limit hit: %s", exc)
            return RuntimeError(
                "Gemini rate limit reached. Please wait a moment before retrying."
            )

        logger.error("Gemini API error: %s", exc)
        return RuntimeError(f"Gemini API error: {exc}")

    async def complete(
        self,
        messages: list[dict[str, Any]],
        model: str = _DEFAULT_CHAT_MODEL,
        max_tokens: int = 1024,
        stream: bool = False,
    ) -> str:
        """Send a chat request to Gemini (non-streaming only)."""
        logger.info("[GEMINI] Starting non-streaming request with %d messages", len(messages))
        client = self._get_client()
        system_instruction, contents = self._to_gemini_contents(messages)
        config = self._build_config(system_instruction, max_tokens)

        try:
            logger.debug("[GEMINI] Sending request to Gemini API")
            response = await client.aio.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
            logger.info("[GEMINI] Non-streaming request completed, response length: %d", len(response.text or ""))
            return response.text or ""
        except Exception as exc:
            logger.error("[GEMINI] Error in complete: %s", exc)
            raise self._handle_gemini_error(exc, model=model) from exc

    async def complete_stream(
        self,
        messages: list[dict[str, Any]],
        model: str = _DEFAULT_CHAT_MODEL,
        max_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]:
        """Send a streaming chat request to Gemini."""
        logger.info("[GEMINI] Starting streaming request with %d messages", len(messages))
        client = self._get_client()
        system_instruction, contents = self._to_gemini_contents(messages)
        config = self._build_config(system_instruction, max_tokens)

        try:
            logger.debug("[GEMINI] Awaiting streaming call to get async iterator")
            # Await the streaming call to get the async iterator
            stream = await client.aio.models.generate_content_stream(
                model=model,
                contents=contents,
                config=config,
            )
            logger.debug("[GEMINI] Got async iterator, starting to iterate chunks")
            # Now iterate over the async iterator
            async for chunk in stream:
                text = getattr(chunk, "text", None)
                if text:
                    logger.debug("[GEMINI] Yielding chunk: %s", text[:50] + "..." if len(text) > 50 else text)
                    yield text
            logger.info("[GEMINI] Streaming request completed successfully")
        except Exception as exc:
            logger.error("[GEMINI] Error in complete_stream: %s", exc)
            raise self._handle_gemini_error(exc, model=model) from exc

    async def _stream_response(
        self,
        client: Any,
        contents: list[Any],
        model: str,
        config: Any,
    ) -> AsyncGenerator[str, None]:
        """Internal async generator that yields streamed Gemini text chunks."""
        try:
            logger.debug("Starting Gemini content stream")
            # Await the streaming call to get the async iterator
            stream = await client.aio.models.generate_content_stream(
                model=model,
                contents=contents,
                config=config,
            )
            # Now iterate over the async iterator
            async for chunk in stream:
                text = getattr(chunk, "text", None)
                if text:
                    logger.debug("Yielding chunk from Gemini stream")
                    yield text
            logger.debug("Gemini content stream completed")
        except Exception as exc:
            logger.error("Error in Gemini stream response: %s", exc)
            raise self._handle_gemini_error(exc, model=model) from exc

    async def transcribe_audio(self, file_path: str) -> str:
        """Transcribe an audio file using Gemini audio input."""
        client = self._get_client()
        mime_type, _ = mimetypes.guess_type(file_path)
        mime_type = mime_type or "audio/wav"

        try:
            with open(file_path, "rb") as audio_file:
                audio_bytes = audio_file.read()

            response = await client.aio.models.generate_content(
                model=_DEFAULT_CHAT_MODEL,
                contents=[
                    types.Part.from_text(text=_DEFAULT_TRANSCRIPTION_PROMPT),
                    types.Part.from_bytes(data=audio_bytes, mime_type=mime_type),
                ],
            )
            return (response.text or "").strip()
        except Exception as exc:
            raise self._handle_gemini_error(exc, model=_DEFAULT_CHAT_MODEL) from exc

    async def generate_speech(self, text: str, voice: str = "onyx") -> bytes:
        """Generate audio bytes from text using Gemini TTS."""
        client = self._get_client()
        gemini_voice = _VOICE_MAP.get(voice.lower(), voice)

        try:
            response = await client.aio.models.generate_content(
                model=_DEFAULT_TTS_MODEL,
                contents=text,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=gemini_voice
                            )
                        )
                    ),
                ),
            )
            audio_data = response.candidates[0].content.parts[0].inline_data.data
            return self._ensure_wav(audio_data)
        except Exception as exc:
            raise self._handle_gemini_error(exc, model=_DEFAULT_TTS_MODEL) from exc

    def _ensure_wav(self, audio_data: bytes) -> bytes:
        if audio_data[:4] == b"RIFF":
            return audio_data

        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(24000)
            wav_file.writeframes(audio_data)
        return wav_buffer.getvalue()


# Module-level singleton
ai_client = AIClient()
