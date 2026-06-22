"""Text-to-speech with a three-tier fallback chain.

Priority:
1. ElevenLabs  — high-quality neural TTS (requires API key + pygame).
2. macOS ``say`` — built-in offline TTS (no key required, macOS only).
3. Print        — last resort; never crashes the assistant.

The ``is_speaking`` flag allows the voice loop to avoid re-triggering the
wake-word detector while MITRA is talking.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import threading

from backend.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Optional dependencies
# ---------------------------------------------------------------------------

try:
    from elevenlabs import ElevenLabs  # type: ignore[import]
    import pygame                       # type: ignore[import]
    _elevenlabs_available = True
except ImportError:
    _elevenlabs_available = False
    logger.info(
        "elevenlabs/pygame not installed — TTS will use macOS 'say' fallback."
    )


class TextToSpeech:
    """Multi-tier TTS wrapper.

    Speaks text via ElevenLabs, macOS ``say``, or console print —
    whichever is available, in that order of preference.
    """

    def __init__(self) -> None:
        """Initialise and configure the TTS engine."""
        self._client       = None
        self._voice_id     = settings.elevenlabs_voice_id
        self._say_available = self._check_say()
        self.is_speaking    = False          # set True while audio is playing
        self._lock          = threading.Lock()

        if _elevenlabs_available:
            api_key = settings.elevenlabs_api_key or os.getenv("ELEVENLABS_API_KEY", "")
            if api_key and api_key not in (
                "your_elevenlabs_api_key_here",
                "your_actual_elevenlabs_api_key_here",
            ):
                try:
                    self._client = ElevenLabs(api_key=api_key)
                    pygame.mixer.init()
                    logger.info(
                        "TTS initialised — ElevenLabs voice_id=%s", self._voice_id
                    )
                except Exception as exc:
                    logger.error("Failed to initialise ElevenLabs: %s", exc)
                    self._client = None
            else:
                logger.info(
                    "ELEVENLABS_API_KEY not configured — "
                    "using %s as TTS fallback.",
                    "macOS say" if self._say_available else "print",
                )

    # ------------------------------------------------------------------
    # Availability helpers
    # ------------------------------------------------------------------

    def _check_say(self) -> bool:
        """Return ``True`` if macOS ``say`` command is available."""
        try:
            result = subprocess.run(
                ["which", "say"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            available = result.returncode == 0
            if available:
                logger.info("macOS 'say' command available as TTS fallback.")
            return available
        except Exception:
            return False

    def is_available(self) -> bool:
        """Return ``True`` if any TTS tier is better than print.

        Returns:
            Boolean availability flag.
        """
        return self._client is not None or self._say_available

    # ------------------------------------------------------------------
    # Public speak method
    # ------------------------------------------------------------------

    def speak(self, text: str) -> None:
        """Convert *text* to speech and block until playback finishes.

        Falls back through ElevenLabs → macOS say → print.

        Args:
            text: The string to be spoken aloud.
        """
        if not text.strip():
            return

        with self._lock:  # prevent concurrent speaks
            self.is_speaking = True
            try:
                if self._client is not None:
                    if self._speak_elevenlabs(text):
                        return
                if self._say_available:
                    if self._speak_say(text):
                        return
                # Final fallback
                print(f"\n[MITRA] {text}\n")
            finally:
                self.is_speaking = False

    # ------------------------------------------------------------------
    # Tier 1: ElevenLabs
    # ------------------------------------------------------------------

    def _speak_elevenlabs(self, text: str) -> bool:
        """Speak via ElevenLabs. Returns True on success."""
        try:
            logger.debug("Generating audio from ElevenLabs...")
            audio_iter = self._client.generate(        # type: ignore[union-attr]
                text=text,
                voice=self._voice_id,
                model="eleven_multilingual_v2",
            )
            audio_bytes = b"".join(audio_iter)

            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            pygame.mixer.music.load(tmp_path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)

            try:
                os.unlink(tmp_path)
            except OSError:
                pass

            logger.debug("ElevenLabs TTS playback complete.")
            return True

        except Exception as exc:
            logger.error("ElevenLabs TTS error: %s — trying next fallback.", exc)
            return False

    # ------------------------------------------------------------------
    # Tier 2: macOS say
    # ------------------------------------------------------------------

    def _speak_say(self, text: str) -> bool:
        """Speak via macOS built-in ``say`` command. Returns True on success."""
        try:
            # Use Alex voice for a clean, neutral tone
            subprocess.run(
                ["say", "-v", "Samantha", text],
                check=True,
                timeout=60,        # generous timeout for long responses
                capture_output=True,
            )
            logger.debug("macOS say TTS complete.")
            return True
        except FileNotFoundError:
            logger.warning("macOS 'say' not found — falling back to print.")
            self._say_available = False
            return False
        except subprocess.TimeoutExpired:
            logger.warning("macOS 'say' timed out.")
            return False
        except Exception as exc:
            logger.error("macOS say error: %s", exc)
            return False
