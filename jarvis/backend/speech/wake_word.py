"""Wake-word detection for the MITRA voice assistant.

Uses keyword matching via Google STT (SpeechRecognition).

Key improvements over v1:
- A single ``sr.Microphone`` context is opened for the *entire* listen loop
  instead of re-opening on every iteration, preventing "device already open"
  errors on macOS.
- ``stop()`` / ``threading.Event`` allow the loop to be interrupted cleanly
  from another thread without killing the process.
- ``on_detected`` optional callback fires when the wake word is heard.

This module is intentionally standalone — it does not import FastAPI or
any async code so it can run in a blocking background thread without
freezing the event loop.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

from backend.config import settings
from backend.speech.stt import SpeechToText
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class WakeWordDetector:
    """Block until the configured wake word is heard.

    Parameters
    ----------
    stt:
        A shared :class:`~backend.speech.stt.SpeechToText` instance.
        Reusing one instance avoids opening multiple conflicting microphone
        streams simultaneously.
    on_detected:
        Optional zero-argument callback called immediately when the wake
        word is detected.  Useful for firing UI state changes without
        blocking the detector loop.
    """

    def __init__(
        self,
        stt: SpeechToText,
        on_detected: Callable[[], None] | None = None,
    ) -> None:
        self._stt        = stt
        self._wake_word  = settings.wake_word.lower().strip()
        self._enabled    = settings.wake_word_enabled
        self._stop_event = threading.Event()
        self._on_detected = on_detected

        logger.info(
            "WakeWordDetector ready (wake_word=%r, enabled=%s)",
            self._wake_word,
            self._enabled,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def wait(self) -> bool:
        """Block until the wake word is detected or ``stop()`` is called.

        If ``wake_word_enabled`` is ``False`` in settings this returns
        immediately — useful for development / text-only mode.

        Returns:
            ``True`` if the wake word was detected, ``False`` if ``stop()``
            was called before detection.
        """
        self._stop_event.clear()

        if not self._enabled:
            logger.debug("Wake word disabled — skipping gate.")
            return True

        if not self._stt.is_available():
            logger.warning(
                "STT not available — skipping wake word gate (mic not found)."
            )
            return True

        return self._listen_loop()

    def stop(self) -> None:
        """Signal the wake word loop to exit on the next iteration.

        Safe to call from any thread.
        """
        self._stop_event.set()
        logger.debug("WakeWordDetector stop requested.")

    def close(self) -> None:
        """Release resources and stop the detector."""
        self.stop()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _listen_loop(self) -> bool:
        """Open a single mic context and continuously listen for the wake word.

        Returns:
            ``True`` if detected, ``False`` if stopped.
        """
        logger.info("Waiting for wake word %r …", self._wake_word)

        try:
            with self._stt.open_source() as source:
                # Single calibration pass for the whole loop
                self._stt.calibrate(source, duration=0.5)

                while not self._stop_event.is_set():
                    # Short phrase to keep latency low while scanning for wake word
                    audio = self._stt.record(source, timeout=4, phrase_time_limit=5)
                    if audio is None:
                        # Timeout — just loop again
                        continue

                    heard = self._stt.transcribe(audio)
                    if not heard:
                        continue

                    lower_heard = heard.lower()
                    # Accept "mitra", "hey mitra", "okay mitra", or legacy "jarvis"
                    if self._wake_word in lower_heard or "hey mitra" in lower_heard or "jarvis" in lower_heard:
                        logger.info("Wake word detected in: %r", heard)
                        if self._on_detected:
                            try:
                                self._on_detected()
                            except Exception as exc:  # pylint: disable=broad-except
                                logger.error("on_detected callback error: %s", exc)
                        return True

                    logger.debug("Wake check heard %r — not wake word.", heard)

        except RuntimeError as exc:
            logger.error("WakeWordDetector: STT unavailable — %s", exc)
        except OSError as exc:
            logger.error("WakeWordDetector: microphone error — %s", exc)
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("WakeWordDetector: unexpected error — %s", exc)
            time.sleep(1)  # Brief pause before potential retry

        return False
