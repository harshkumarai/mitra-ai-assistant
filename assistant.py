"""
assistant.py
------------
Core assistant loop.
Ties together speech I/O, wake-word detection, and the MITRA Gemini chat engine.
"""

import asyncio
import sys
import traceback
from pathlib import Path

from utilities.speech import SpeechEngine
from utilities.wake_word import WakeWordDetector
from utilities.logger import get_logger
from memory.context import ConversationContext
from memory.history import CommandHistory

# Wire into the jarvis/ chat engine so the voice loop shares the same
# Gemini pipeline and conversation memory as the web frontend.
_JARVIS_DIR = Path(__file__).resolve().parent / "jarvis"
if str(_JARVIS_DIR) not in sys.path:
    sys.path.insert(0, str(_JARVIS_DIR))

from backend.ai.chat_engine import chat_engine          # noqa: E402
from backend.database.connection import init_db         # noqa: E402

logger = get_logger(__name__)

# Fixed session ID so voice conversations are stored in the same DB session
_VOICE_SESSION_ID = "voice-assistant"


class VoiceAssistant:

    def __init__(self):
        logger.info("[INIT] Creating SpeechEngine…")
        self.speech = SpeechEngine()
        logger.info("[INIT] SpeechEngine ready. STT=%s, TTS=%s",
                    self.speech._stt_mode, self.speech._tts_mode)

        logger.info("[INIT] Creating WakeWordDetector…")
        self.wake_word = WakeWordDetector(self.speech)
        logger.info("[INIT] WakeWordDetector ready.")

        self.context = ConversationContext()
        self.history = CommandHistory()

        # Ensure the database tables exist before any chat_engine call.
        asyncio.run(init_db())

        logger.info("[INIT] VoiceAssistant fully initialised.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self):
        """Main assistant loop — blocks until the user says 'exit' or Ctrl+C."""
        logger.info("[RUN] Entering run() loop.")
        try:
            self.speech.speak("MITRA is online and ready to assist. Waiting for wake word.")

            while True:
                logger.info("[RUN] Waiting for wake word…")
                self._wait_for_wake_word()

                # Acknowledge wake word
                self.speech.speak("Yes sir, how can I help you?")

                logger.info("[RUN] Listening for command…")
                user_input = self.speech.listen()
                logger.info("[RUN] Heard: '%s'", user_input)

                if not user_input:
                    self.speech.speak("I did not catch that. Please try again.")
                    continue

                print(f"\n── Command ──────────────────────────\n  {user_input}\n─────────────────────────────────────")

                if user_input.strip().lower() in ("quit", "exit", "bye", "goodbye"):
                    self.speech.speak("Goodbye, Sir.")
                    logger.info("[RUN] Exit command received.")
                    break

                response = self._process(user_input)
                self.speech.speak(response)

        except KeyboardInterrupt:
            logger.info("[RUN] Interrupted by user (Ctrl+C).")
            self.speech.speak("Goodbye, Sir.")
        except Exception:
            logger.error("[RUN] Unhandled exception:\n%s", traceback.format_exc())
            raise

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _wait_for_wake_word(self):
        logger.debug("[WAKE] Calling wake_word.wait()…")
        self.wake_word.wait()
        logger.debug("[WAKE] wake_word.wait() returned.")

    def _process(self, text: str) -> str:
        """Send user text through the MITRA Gemini chat engine and return the reply."""
        self.context.add_turn(role="user", content=text)
        try:
            # Use the same chat_engine as the web frontend
            response_text, _ = asyncio.run(
                chat_engine.chat(_VOICE_SESSION_ID, text)
            )
        except Exception:
            logger.error("[PROCESS] chat_engine error:\n%s", traceback.format_exc())
            response_text = "Sorry, I encountered an error processing your request."

        self.history.save(user_input=text, response=response_text)
        self.context.add_turn(role="assistant", content=response_text)
        return response_text
