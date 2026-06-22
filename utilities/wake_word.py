"""
utilities/wake_word.py
----------------------
Wake-word detection. Receives the shared SpeechEngine so it never
creates a second mic/TTS instance that would conflict with the main one.

Two modes:
  1. Porcupine  — on-device, needs API key + .ppn file in .env
  2. STT fallback — uses Google STT to listen for the wake phrase
  3. Text mode   — no wake word needed, passes through immediately
"""

import config
from utilities.logger import get_logger

logger = get_logger(__name__)


class WakeWordDetector:
    """Blocks until the configured wake word is detected (or passes straight
    through in text mode)."""

    def __init__(self, speech_engine=None):
        """
        Parameters
        ----------
        speech_engine : SpeechEngine
            The shared engine from VoiceAssistant. Passed in to avoid
            creating a conflicting second instance.
        """
        self._speech = speech_engine
        self._use_porcupine = bool(
            config.PORCUPINE_ACCESS_KEY and config.PORCUPINE_KEYWORD_PATH
        )

        if self._use_porcupine:
            self._init_porcupine()
        else:
            logger.info("Porcupine not configured — using keyword fallback for wake word.")

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def _init_porcupine(self):
        try:
            import pvporcupine, pyaudio, struct
            self._porcupine = pvporcupine.create(
                access_key=config.PORCUPINE_ACCESS_KEY,
                keyword_paths=[config.PORCUPINE_KEYWORD_PATH],
            )
            self._pa = pyaudio.PyAudio()
            self._stream = self._pa.open(
                rate=self._porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=self._porcupine.frame_length,
            )
            self._struct = struct
            logger.info("Porcupine wake-word detector initialised.")
        except Exception as exc:
            logger.warning("Porcupine init failed (%s) — falling back to STT.", exc)
            self._use_porcupine = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def wait(self) -> None:
        """Block until the wake word is detected."""
        if self._use_porcupine:
            self._wait_porcupine()
        else:
            self._wait_fallback()

    # ------------------------------------------------------------------
    # Backends
    # ------------------------------------------------------------------

    def _wait_porcupine(self) -> None:
        logger.debug("Porcupine listening for wake word…")
        while True:
            pcm = self._stream.read(
                self._porcupine.frame_length, exception_on_overflow=False
            )
            pcm_unpacked = self._struct.unpack_from(
                "h" * self._porcupine.frame_length, pcm
            )
            if self._porcupine.process(pcm_unpacked) >= 0:
                logger.info("Wake word detected via Porcupine.")
                return

    def _wait_fallback(self) -> None:
        # Text mode — skip gate
        if self._speech and not self._speech._audio_mode:
            logger.debug("Text mode — skipping wake word gate.")
            return

        # Wake word disabled in config — skip gate
        if not config.WAKE_WORD_ENABLED:
            logger.debug("Wake word disabled — skipping gate.")
            return

        # Voice mode — listen via STT for the wake phrase
        logger.debug("Listening for wake word '%s'…", config.WAKE_WORD)
        while True:
            heard = self._speech.listen() if self._speech else ""
            logger.debug("Wake word check heard: '%s'", heard)
            if config.WAKE_WORD.lower() in heard.lower():
                logger.info("Wake word detected via STT fallback.")
                return

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def __del__(self):
        if getattr(self, '_use_porcupine', False):
            try:
                self._stream.close()
                self._pa.terminate()
                self._porcupine.delete()
            except Exception:
                pass
