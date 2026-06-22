"""
config.py
---------
Central configuration file for the voice assistant.
All tunable settings (language, voice rate, wake word, API keys, paths)
live here so every module can import from a single source of truth.
Load secrets from a .env file so they are never hard-coded.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Determine project paths
PROJECT_ROOT = Path(__file__).resolve().parent
JARVIS_ENV_PATH = PROJECT_ROOT / "jarvis" / ".env"

# Load variables from jarvis/.env file (where the API keys actually are)
if JARVIS_ENV_PATH.exists():
    load_dotenv(dotenv_path=JARVIS_ENV_PATH)
    print(f"[CONFIG] Loaded .env from: {JARVIS_ENV_PATH}")
else:
    print(f"[CONFIG] WARNING: .env not found at {JARVIS_ENV_PATH}")
    # Fallback to root .env if it exists
    load_dotenv()

# ---------------------------------------------------------------------------
# Speech Recognition
# ---------------------------------------------------------------------------
RECOGNITION_LANGUAGE = "en-US"          # BCP-47 language tag for Google STT
MICROPHONE_INDEX = 2                     # MacBook Air Microphone
LISTEN_TIMEOUT_SECONDS = 10             # Max seconds to wait for speech start
PHRASE_TIME_LIMIT_SECONDS = 10          # Max seconds for a single phrase
NOISE_CALIBRATION_SECONDS = 2           # Ambient noise calibration before each listen

# ---------------------------------------------------------------------------
# Text-to-Speech (ElevenLabs)
# ---------------------------------------------------------------------------
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "auq43ws1oslv0tO4BDa7")

# Legacy pyttsx3 settings (kept for reference, no longer used)
TTS_RATE = 175          # Words per minute
TTS_VOLUME = 1.0        # 0.0 – 1.0
TTS_VOICE_INDEX = 0     # 0 = first available system voice

# ---------------------------------------------------------------------------
# Wake Word (Porcupine)
# ---------------------------------------------------------------------------
WAKE_WORD = "mitra"                     # Wake phrase — spoken to activate the assistant
WAKE_WORD_ENABLED = True               # Require wake word before each command
PORCUPINE_ACCESS_KEY = os.getenv("PORCUPINE_ACCESS_KEY", "")
PORCUPINE_KEYWORD_PATH = os.getenv("PORCUPINE_KEYWORD_PATH", "")  # .ppn file

# ---------------------------------------------------------------------------
# Gemini (optional - used for fallback NLU)
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash"

# Debug: Log API key status (without exposing the actual key)
if GEMINI_API_KEY:
    print(f"[CONFIG] GEMINI_API_KEY detected (length: {len(GEMINI_API_KEY)})")
else:
    print("[CONFIG] WARNING: GEMINI_API_KEY not found or empty!")

# ---------------------------------------------------------------------------
# Memory / Persistence
# ---------------------------------------------------------------------------
HISTORY_FILE_PATH = "memory/history.json"   # Where command history is stored
MAX_CONTEXT_TURNS = 10                      # Short-term context window size

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_FILE_PATH = "assistant.log"
LOG_LEVEL = "INFO"      # DEBUG | INFO | WARNING | ERROR | CRITICAL
