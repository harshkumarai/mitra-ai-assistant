"""Speech-to-text using Google Speech Recognition via the SpeechRecognition library.

Improvements over v1:
- Graceful mic auto-detection when the configured index is unavailable.
- Single-instance mic context exposed via ``open_source()`` to allow
  wake-word detection and command listening to share one stream.
- All public methods return empty string on failure (never raise).
"""

from __future__ import annotations

import contextlib
from typing import Generator

from backend.config import settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)

try:
    import speech_recognition as sr  # type: ignore[import]
    _sr_available = True
except ImportError:
    _sr_available = False
    logger.warning("speech_recognition not installed — STT features disabled.")


def _resolve_mic_index() -> int | None:
    """Return the configured mic index, or None if auto-detection is needed."""
    idx = settings.microphone_index
    if idx < 0:
        return None
    # Verify the index actually exists
    if not _sr_available:
        return None
    try:
        mics = sr.Microphone.list_microphone_names()
        if idx < len(mics):
            return idx
        logger.warning(
            "Configured MICROPHONE_INDEX=%d not found (%d mics available). "
            "Falling back to default mic.",
            idx, len(mics),
        )
    except Exception as exc:
        logger.warning("Could not enumerate microphones: %s", exc)
    return None


class SpeechToText:
    """Microphone-based speech transcription.

    Uses :pypi:`SpeechRecognition` with the Google Web Speech API backend.
    PyAudio is required for microphone access; if it is absent the class
    degrades gracefully.
    """

    def __init__(self) -> None:
        """Initialise the recogniser and resolve the microphone index."""
        self._recognizer: "sr.Recognizer | None" = sr.Recognizer() if _sr_available else None
        self._mic_index: int | None = _resolve_mic_index()

        if _sr_available:
            logger.info(
                "SpeechToText ready — mic_index=%s",
                self._mic_index if self._mic_index is not None else "default",
            )

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Return ``True`` if speech recognition libraries are installed.

        Returns:
            Boolean availability flag.
        """
        return _sr_available and self._recognizer is not None

    # ------------------------------------------------------------------
    # Mic context (for sharing one mic between wake-word and command listen)
    # ------------------------------------------------------------------

    @contextlib.contextmanager
    def open_source(self) -> Generator["sr.AudioSource", None, None]:
        """Context manager that opens and yields a single ``sr.Microphone``.

        Usage::

            with stt.open_source() as source:
                audio = stt.record(source)
            text = stt.transcribe(audio)

        Yields:
            :class:`speech_recognition.AudioSource` instance.

        Raises:
            RuntimeError: If STT is not available.
        """
        if not self.is_available():
            raise RuntimeError("STT not available")
        with sr.Microphone(device_index=self._mic_index) as source:  # type: ignore[union-attr]
            yield source

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def calibrate(self, source: "sr.AudioSource", duration: float = 0.5) -> None:
        """Adjust the recogniser for ambient noise.

        Args:
            source: An open :class:`~speech_recognition.AudioSource`.
            duration: Calibration duration in seconds.
        """
        if self._recognizer is None:
            return
        try:
            self._recognizer.adjust_for_ambient_noise(source, duration=duration)  # type: ignore[union-attr]
        except Exception as exc:
            logger.debug("Calibration skipped: %s", exc)

    def record(
        self,
        source: "sr.AudioSource",
        timeout: int = 4,
        phrase_time_limit: int = 8,
    ) -> "sr.AudioData | None":
        """Record a single utterance from an already-open *source*.

        Args:
            source: An open :class:`~speech_recognition.AudioSource`.
            timeout: Seconds to wait for speech to start.
            phrase_time_limit: Max seconds of recording per phrase.

        Returns:
            :class:`~speech_recognition.AudioData` or ``None`` on timeout.
        """
        if self._recognizer is None:
            return None
        try:
            return self._recognizer.listen(  # type: ignore[union-attr]
                source,
                timeout=timeout,
                phrase_time_limit=phrase_time_limit,
            )
        except sr.WaitTimeoutError:
            logger.debug("STT timed out waiting for speech.")
        except Exception as exc:
            logger.error("STT record error: %s", exc)
        return None

    def transcribe(self, audio: "sr.AudioData") -> str:
        """Transcribe a recorded :class:`~speech_recognition.AudioData` object.

        Args:
            audio: Audio to transcribe.

        Returns:
            Transcribed text or empty string.
        """
        if self._recognizer is None or audio is None:
            return ""
        try:
            text = self._recognizer.recognize_google(audio)  # type: ignore[union-attr]
            logger.info("STT recognised: %s", text)
            return str(text)
        except sr.UnknownValueError:
            logger.debug("STT could not understand audio.")
        except sr.RequestError as exc:
            logger.error("STT Google API request failed: %s", exc)
        except Exception as exc:
            logger.error("Unexpected STT transcribe error: %s", exc)
        return ""

    # ------------------------------------------------------------------
    # Convenience one-shot method (kept for backward compatibility)
    # ------------------------------------------------------------------

    def listen(
        self,
        timeout: int = 10,
        calibration_seconds: float = 0.5,
        phrase_time_limit: int = 10,
    ) -> str:
        """Open mic, calibrate, record one phrase, and return transcription.

        This is a convenience wrapper.  For lower latency in a continuous
        loop use :meth:`open_source` / :meth:`record` / :meth:`transcribe`
        directly.

        Args:
            timeout: Seconds to wait for speech to begin.
            calibration_seconds: Ambient-noise calibration duration.
            phrase_time_limit: Max recording seconds per phrase.

        Returns:
            Transcribed text, or an empty string if nothing was recognised.
        """
        if not self.is_available():
            logger.warning("STT unavailable — returning empty string.")
            return ""

        try:
            with sr.Microphone(device_index=self._mic_index) as source:  # type: ignore[union-attr]
                logger.debug("Calibrating for ambient noise (%.1fs)…", calibration_seconds)
                self._recognizer.adjust_for_ambient_noise(source, duration=calibration_seconds)  # type: ignore[union-attr]
                logger.debug("Listening… (timeout=%ds)", timeout)
                audio = self._recognizer.listen(  # type: ignore[union-attr]
                    source, timeout=timeout, phrase_time_limit=phrase_time_limit
                )
            return self.transcribe(audio)

        except sr.WaitTimeoutError:
            logger.debug("STT timed out waiting for speech.")
        except OSError as exc:
            logger.error("STT microphone error: %s", exc)
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Unexpected STT error: %s", exc)

        return ""
