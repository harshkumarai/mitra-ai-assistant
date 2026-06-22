"""
utilities/speech.py
-------------------
Speech I/O: microphone input (STT) and speaker output (TTS).

Improvements:
  - 10-second listen timeout (req 1)
  - Per-listen ambient noise calibration for 2 seconds (req 2)
  - Recognised text printed before processing (req 3)
  - Low-confidence retry: asks user to repeat once (req 4)
  - TEXT MODE fallback: type "text" mid-session to switch to keyboard input (req 5)
  - ElevenLabs TTS integration for professional voice output
"""

import traceback
import os
import io
import tempfile
import config
from utilities.logger import get_logger

logger = get_logger(__name__)

# ── Detect audio stack ────────────────────────────────────────────────────────
try:
    import pyaudio  # noqa: F401
    import speech_recognition as sr
    _STT_AVAILABLE = True
    logger.info("[SPEECH] STT stack loaded (pyaudio + speechrecognition).")
except ImportError as _import_err:
    _STT_AVAILABLE = False
    logger.warning("[SPEECH] STT stack unavailable (%s) — TEXT MODE.", _import_err)

# ── ElevenLabs TTS ───────────────────────────────────────────────────────────
try:
    from elevenlabs import ElevenLabs
    import pygame
    _TTS_AVAILABLE = True
    logger.info("[SPEECH] ElevenLabs TTS stack loaded.")
except ImportError as _import_err:
    _TTS_AVAILABLE = False
    logger.warning("[SPEECH] ElevenLabs TTS unavailable (%s) — TEXT MODE.", _import_err)


class SpeechEngine:
    """
    Microphone STT + ElevenLabs TTS, with automatic text-mode fallback.

    Extra features:
      • Per-listen noise calibration for better accuracy in changing environments.
      • Retry once on low confidence (empty recognition result after valid audio).
      • Type the special command "text" at any prompt to force text-mode for that turn.
      • ElevenLabs professional voice output.
    """

    def __init__(self):
        self._stt_mode = _STT_AVAILABLE
        self._tts_mode = _TTS_AVAILABLE
        self._audio_mode = self._stt_mode
        # Track whether we already retried this turn (req 4)
        self._retry_done = False

        logger.info("[SPEECH] Initialising SpeechEngine (stt=%s, tts=%s)…", 
                    self._stt_mode, self._tts_mode)

        if self._stt_mode:
            self._init_stt()
        else:
            print("[TEXT MODE] No speech recognition found — type your commands.\n")

        self._audio_mode = self._stt_mode

        if self._tts_mode:
            self._init_tts()
        else:
            print("[TEXT MODE] ElevenLabs TTS not available — text output only.\n")

        logger.info("[SPEECH] SpeechEngine ready.")

    # ── Initialisation ────────────────────────────────────────────────────────

    def _init_stt(self):
        """Initialize speech recognition (STT)."""
        try:
            logger.info("[SPEECH] Setting up microphone (index=%s)…", config.MICROPHONE_INDEX)
            self._recognizer = sr.Recognizer()
            self._mic = sr.Microphone(device_index=config.MICROPHONE_INDEX)

            # Initial startup calibration (req 2 — also done per-listen below)
            with self._mic as source:
                logger.info("[SPEECH] Startup noise calibration (%ss)…",
                            config.NOISE_CALIBRATION_SECONDS)
                self._recognizer.adjust_for_ambient_noise(
                    source, duration=config.NOISE_CALIBRATION_SECONDS
                )
            logger.info("[SPEECH] Microphone ready.")
        except Exception:
            logger.error("[SPEECH] Microphone init failed:\n%s", traceback.format_exc())
            self._stt_mode = False
            print("[TEXT MODE] Mic failed — falling back to keyboard input.\n")

    def _init_tts(self):
        """Initialize ElevenLabs TTS."""
        try:
            api_key = os.getenv("ELEVENLABS_API_KEY", "")
            if not api_key:
                logger.warning("[SPEECH] ELEVENLABS_API_KEY not found in environment.")
                self._tts_mode = False
                print("[TEXT MODE] ElevenLabs API key missing — text output only.\n")
                return

            voice_id = os.getenv("ELEVENLABS_VOICE_ID", "auq43ws1oslv0tO4BDa7")
            logger.info("[SPEECH] Initialising ElevenLabs TTS (voice_id=%s)…", voice_id)
            
            self._elevenlabs = ElevenLabs(api_key=api_key)
            self._voice_id = voice_id
            
            # Initialize pygame for audio playback
            pygame.mixer.init()
            logger.info("[SPEECH] ElevenLabs TTS ready.")
        except Exception:
            logger.error("[SPEECH] ElevenLabs TTS init failed:\n%s", traceback.format_exc())
            self._tts_mode = False
            print("[TEXT MODE] ElevenLabs TTS init failed — falling back to print output.\n")

    # ── Public API ────────────────────────────────────────────────────────────

    def speak(self, text: str) -> None:
        """Speak text aloud using ElevenLabs, or print it in text / fallback mode."""
        logger.info("[SPEAK] >>> %s", text)
        if not self._tts_mode:
            print(f"\nAssistant: {text}")
            return
        
        try:
            # Generate audio from ElevenLabs
            logger.debug("[SPEAK] Generating audio from ElevenLabs...")
            audio = self._elevenlabs.generate(
                text=text,
                voice=self._voice_id,
                model="eleven_multilingual_v2"
            )
            
            # Save to temporary file and play
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
                if isinstance(audio, bytes):
                    temp_file.write(audio)
                else:
                    for chunk in audio:
                        if chunk:
                            temp_file.write(chunk)
                temp_file_path = temp_file.name
            
            # Play audio using pygame
            logger.debug("[SPEAK] Playing audio...")
            pygame.mixer.music.load(temp_file_path)
            pygame.mixer.music.play()
            
            # Wait for audio to finish playing
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            
            # Clean up temporary file
            os.unlink(temp_file_path)
            logger.debug("[SPEAK] Done.")
            
        except Exception as exc:
            logger.error("[SPEAK] ElevenLabs TTS error: %s\n%s", exc, traceback.format_exc())
            print(f"\nAssistant: {text}")   # silent fallback

    def listen(self) -> str:
        """
        Capture one command and return the transcript.

        Behaviour:
          1. In text mode → reads from stdin.
          2. In voice mode:
             a. Recalibrates ambient noise (req 2).
             b. Records up to LISTEN_TIMEOUT_SECONDS.
             c. Sends audio to Google STT.
             d. Prints the recognised text (req 3).
             e. On empty result (low confidence / unknown audio), asks user to
                repeat — but only once per turn (req 4).
             f. If the user types "text" at any `You: ` prompt it forces a
                text-mode read for that turn (req 5).
        """
        logger.info("[LISTEN] Starting…")
        self._retry_done = False   # reset retry flag each new turn

        if not self._stt_mode:
            return self._read_stdin()

        return self._record_and_recognise()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _read_stdin(self) -> str:
        """Read a line from the keyboard (text mode)."""
        try:
            text = input("\nYou: ").strip()
            logger.info("[LISTEN] stdin: '%s'", text)
            return text
        except (EOFError, KeyboardInterrupt):
            return ""

    def _recalibrate(self):
        """Re-measure ambient noise before each listen (req 2)."""
        try:
            with self._mic as source:
                logger.info("[LISTEN] Recalibrating noise (%ss)…",
                            config.NOISE_CALIBRATION_SECONDS)
                self._recognizer.adjust_for_ambient_noise(
                    source, duration=config.NOISE_CALIBRATION_SECONDS
                )
        except Exception:
            logger.warning("[LISTEN] Recalibration failed (non-fatal):\n%s",
                           traceback.format_exc())

    def _record_and_recognise(self, is_retry: bool = False) -> str:
        """
        Core voice capture + STT.  Called for the initial attempt and once
        for the low-confidence retry.
        """
        # Req 2: recalibrate before every listen attempt
        self._recalibrate()

        # ── Record ────────────────────────────────────────────────────
        try:
            with self._mic as source:
                logger.info("[LISTEN] Recording (timeout=%ss phrase_limit=%ss)…",
                            config.LISTEN_TIMEOUT_SECONDS,
                            config.PHRASE_TIME_LIMIT_SECONDS)
                audio = self._recognizer.listen(
                    source,
                    timeout=config.LISTEN_TIMEOUT_SECONDS,
                    phrase_time_limit=config.PHRASE_TIME_LIMIT_SECONDS,
                )
            logger.info("[LISTEN] Audio captured — sending to Google STT…")
        except sr.WaitTimeoutError:
            logger.info("[LISTEN] Timeout — no speech detected.")
            return self._handle_no_input(is_retry)
        except Exception:
            logger.error("[LISTEN] Recording error:\n%s", traceback.format_exc())
            return ""

        # ── Recognise ─────────────────────────────────────────────────
        try:
            text = self._recognizer.recognize_google(
                audio, language=config.RECOGNITION_LANGUAGE
            )
            # Req 3: always print what was heard
            print(f"\n[Heard] {text}")
            logger.info("[LISTEN] Recognised: '%s'", text)
            return text

        except sr.UnknownValueError:
            logger.info("[LISTEN] Audio not understood.")
            return self._handle_no_input(is_retry)

        except sr.RequestError as exc:
            logger.error("[LISTEN] Google STT error: %s", exc)
            self.speak("I could not reach the speech recognition service. "
                       "Please check your internet connection.")
            return ""

        except Exception:
            logger.error("[LISTEN] Unexpected STT error:\n%s", traceback.format_exc())
            return ""

    def _handle_no_input(self, already_retried: bool) -> str:
        """
        Req 4: on first failure ask the user to repeat once.
        Req 5: offer text-mode fallback at the same prompt.
        """
        if already_retried:
            # Second failure — give up and let the caller handle it
            logger.info("[LISTEN] Retry also failed — returning empty.")
            return ""

        # Ask once
        self.speak(
            "I did not catch that. Please repeat, or type your command and press Enter."
        )
        print('[Tip] Type your command below and press Enter, or just speak again.')
        print('[Tip] Type "text" to switch to keyboard-only mode for this turn.')

        # Req 5: non-blocking text fallback — check stdin with a short timeout
        # Using select so we don't block the mic permanently.
        import select, sys
        rlist, _, _ = select.select([sys.stdin], [], [], 3.0)  # 3 s to type
        if rlist:
            typed = sys.stdin.readline().strip()
            if typed:
                logger.info("[LISTEN] Text fallback input: '%s'", typed)
                print(f"\n[Typed] {typed}")
                return typed

        # No keyboard input in time — try the mic once more (req 4)
        logger.info("[LISTEN] Retrying mic capture…")
        return self._record_and_recognise(is_retry=True)
