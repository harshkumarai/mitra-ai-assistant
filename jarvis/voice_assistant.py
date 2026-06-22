#!/usr/bin/env python3
"""MITRA Voice Assistant — production-ready standalone entry point.

Architecture
------------
This script runs as a **separate process** from the FastAPI server.
A blocking mic loop must never run inside an async event loop — it would
freeze all WebSocket connections and HTTP routes.

Voice loop sequence
-------------------
1. Initialise STT, TTS, WakeWordDetector.
2. Run a single persistent asyncio event loop.
3. Blocking mic operations run in a thread executor (``loop.run_in_executor``).
4. State changes are broadcast to the frontend via HTTP POST →
   ``/api/v1/voice/state`` which fans out over ``/ws/voice-state``.

States
------
idle          → Blue  orb: waiting for wake word
listening     → Orange orb: wake word heard, listening for command
processing    → Purple orb: AI / command dispatcher running
speaking      → Green  orb: TTS playback in progress
error         → Red    orb: unrecoverable mic / API failure

Usage
-----
    cd jarvis/
    python3 voice_assistant.py
"""

from __future__ import annotations

import asyncio
import hashlib
import sys
import traceback
from enum import Enum
from pathlib import Path

# Ensure the jarvis/ directory is on sys.path so backend.* imports resolve
_JARVIS_DIR = Path(__file__).resolve().parent
if str(_JARVIS_DIR) not in sys.path:
    sys.path.insert(0, str(_JARVIS_DIR))

import httpx

from backend.ai.chat_engine import chat_engine
from backend.commands.dispatcher import dispatch
from backend.config import settings
from backend.database.connection import init_db
from backend.speech.stt import SpeechToText
from backend.speech.tts import TextToSpeech
from backend.speech.wake_word import WakeWordDetector
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Fixed session ID — all voice conversations share the same DB thread
_VOICE_SESSION_ID = "voice-assistant"

# Base URL of the running FastAPI server
_SERVER_BASE = f"http://127.0.0.1:{settings.jarvis_port}"


# ---------------------------------------------------------------------------
# State enum
# ---------------------------------------------------------------------------

class AssistantState(str, Enum):
    IDLE         = "idle"
    LISTENING    = "listening"
    PROCESSING   = "processing"
    SPEAKING     = "speaking"
    ERROR        = "error"


# ---------------------------------------------------------------------------
# VoiceAssistant
# ---------------------------------------------------------------------------

class VoiceAssistant:
    """Continuous wake-word → listen → respond loop with state machine."""

    def __init__(self) -> None:
        logger.info("Initialising MITRA Voice Assistant…")

        self._stt  = SpeechToText()
        self._tts  = TextToSpeech()
        self._wake = WakeWordDetector(self._stt)

        if not self._stt.is_available():
            logger.warning(
                "SpeechToText unavailable — mic not detected or "
                "speech_recognition not installed.  Falling back to keyboard input."
            )

        self._loop:               asyncio.AbstractEventLoop | None = None
        self._state:              AssistantState = AssistantState.IDLE
        self._last_response_hash: str            = ""

        logger.info("MITRA Voice Assistant initialised.")

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Run the async voice loop.  Ctrl+C exits cleanly."""
        self._loop = asyncio.get_running_loop()

        # Initialise DB (creates tables if absent)
        await init_db()

        # Seed Harsh as the user name if not already set
        await self._ensure_user_name()

        self._tts_speak("MITRA is online and ready to assist. Say 'Mitra' to activate, Harsh.")
        logger.info("Entering voice loop.  Wake word: %r", settings.wake_word)

        try:
            while True:
                await self._set_state(AssistantState.IDLE, "Waiting for wake word…")

                # ── Wait for wake word ─────────────────────────────────
                detected = await self._loop.run_in_executor(None, self._wake.wait)
                if not detected:
                    # stop() was called externally — exit cleanly
                    break

                # ── Wake word heard ────────────────────────────────────
                await self._set_state(AssistantState.LISTENING, "Listening for command…")
                self._tts_speak("Yes, Harsh?")

                # ── Record command ─────────────────────────────────────
                user_text = await self._listen_for_command()
                if not user_text:
                    self._tts_speak("I didn't catch that.  Please try again.")
                    continue

                logger.info("User said: %r", user_text)
                print(f"\n[You]    {user_text}")

                if user_text.strip().lower() in {"quit", "exit", "bye", "goodbye"}:
                    self._tts_speak("Goodbye, Harsh. Shutting down.")
                    break

                # ── Process ────────────────────────────────────────────
                await self._set_state(AssistantState.PROCESSING, f"Processing: {user_text[:60]}")
                response = await self._process(user_text)

                # Duplicate-response guard
                resp_hash = hashlib.md5(response.encode()).hexdigest()
                if resp_hash == self._last_response_hash:
                    logger.warning("Duplicate response detected — skipping TTS.")
                    continue
                self._last_response_hash = resp_hash

                print(f"[MITRA] {response}\n")

                # ── Speak ──────────────────────────────────────────────
                await self._set_state(AssistantState.SPEAKING, response[:80])
                self._tts_speak(response)

        except KeyboardInterrupt:
            logger.info("Interrupted by Ctrl+C.")
            self._tts_speak("Goodbye, Harsh.")
        except Exception:
            logger.error("Unhandled exception in voice loop:\n%s", traceback.format_exc())
            await self._set_state(AssistantState.ERROR, "Unhandled error")
            raise
        finally:
            self._wake.stop()
            await self._set_state(AssistantState.IDLE, "Offline")

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    async def _set_state(self, state: AssistantState, text: str = "") -> None:
        """Update internal state and broadcast to the frontend."""
        self._state = state
        await self._post_state(state.value, text)

    async def _post_state(self, state: str, text: str = "") -> None:
        """HTTP POST the new state to FastAPI, which fans it out over WS."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                await client.post(
                    f"{_SERVER_BASE}/api/v1/voice/state",
                    json={"state": state, "text": text},
                )
        except Exception as exc:
            logger.debug("Could not post voice state (server may be offline): %s", exc)

    # ------------------------------------------------------------------
    # Audio helpers
    # ------------------------------------------------------------------

    async def _listen_for_command(self) -> str:
        """Listen for one command phrase.  Runs STT in thread executor."""
        assert self._loop is not None
        if not self._stt.is_available():
            # Keyboard fallback
            try:
                return input("\n[Text input] You: ").strip()
            except (EOFError, KeyboardInterrupt):
                return ""
        return await self._loop.run_in_executor(
            None,
            lambda: self._stt.listen(timeout=8, calibration_seconds=0.3, phrase_time_limit=12),
        )

    def _tts_speak(self, text: str) -> None:
        """Speak *text* synchronously — runs inside the current thread."""
        if text.strip():
            self._tts.speak(text)

    # ------------------------------------------------------------------
    # AI / command processing
    # ------------------------------------------------------------------

    async def _process(self, text: str) -> str:
        """Route text through command dispatcher then AI.

        Args:
            text: Transcribed user utterance.

        Returns:
            Response string to speak.
        """
        # 1. Try command dispatcher first (open apps, set volume, reminders…)
        try:
            command_result = await dispatch(text, _VOICE_SESSION_ID)
            if command_result is not None:
                logger.info("Command dispatcher handled: %r", command_result[:80])
                return command_result
        except Exception as exc:
            logger.error("Command dispatcher error: %s", exc)

        # 2. Fall through to Gemini AI (voice_mode=True → concise replies)
        try:
            response_text, _ = await chat_engine.chat(
                _VOICE_SESSION_ID, text, voice_mode=True
            )
            return response_text
        except Exception as exc:
            logger.error("chat_engine error: %s", exc)
            return "Sorry, I encountered an error processing your request."

    # ------------------------------------------------------------------
    # Misc helpers
    # ------------------------------------------------------------------

    async def _ensure_user_name(self) -> None:
        """Seed 'Harsh' as the default user name if not already stored."""
        try:
            from backend.database.connection import get_db
            async for db in get_db():
                async with db.execute(
                    "SELECT value FROM user_preferences WHERE key = 'user_name'"
                ) as cursor:
                    row = await cursor.fetchone()

            if row is None:
                async for db in get_db():
                    await db.execute(
                        "INSERT INTO user_preferences (key, value) VALUES ('user_name', 'Harsh') "
                        "ON CONFLICT(key) DO NOTHING",
                    )
                    await db.commit()
                logger.info("Default user name 'Harsh' seeded into user_preferences.")
        except Exception as exc:
            logger.warning("Could not seed user name: %s", exc)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Print diagnostics and start the async voice loop."""
    print("=" * 58)
    print("  MITRA Voice Assistant")
    print("=" * 58)
    print(f"  Wake word  : {settings.wake_word!r}  (also: 'Hey Mitra')")
    print(f"  Mic index  : {settings.microphone_index}")
    print(f"  Server     : http://127.0.0.1:{settings.jarvis_port}")
    print(f"  Gemini key : {'set' if settings.gemini_api_key else 'MISSING'}")
    el_key = settings.elevenlabs_api_key
    el_ok  = el_key and el_key not in ("your_actual_elevenlabs_api_key_here", "your_elevenlabs_api_key_here")
    print(f"  ElevenLabs : {'set' if el_ok else 'not set → macOS say fallback'}")
    print("=" * 58)
    print()

    if not settings.gemini_api_key:
        print("[ERROR] GEMINI_API_KEY is not set — cannot generate responses.")
        print("        Add it to jarvis/.env and restart.")
        sys.exit(1)

    assistant = VoiceAssistant()
    asyncio.run(assistant.run())


if __name__ == "__main__":
    main()
