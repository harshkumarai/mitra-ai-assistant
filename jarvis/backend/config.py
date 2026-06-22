"""Application configuration via pydantic-settings."""

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parent
MITRA_ROOT = BACKEND_DIR.parent
WORKSPACE_ROOT = MITRA_ROOT.parent

ENV_FILES = (
    WORKSPACE_ROOT / ".env",
    MITRA_ROOT / ".env",
)


def _env_file_has_key(env_path: Path, key: str) -> bool:
    """Return True when *env_path* contains an assignment for *key*."""
    if not env_path.exists():
        return False

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and stripped.split("=", 1)[0].strip() == key:
            return True
    return False


def _load_env() -> str:
    """Load project .env files and return the GEMINI_API_KEY source label."""
    if os.getenv("GEMINI_API_KEY"):
        return "process environment"

    loaded_files: list[Path] = []
    for env_path in ENV_FILES:
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=False)
            loaded_files.append(env_path)

    if os.getenv("GEMINI_API_KEY"):
        for env_path in loaded_files:
            if _env_file_has_key(env_path, "GEMINI_API_KEY"):
                return str(env_path)
        return "loaded .env file"

    if loaded_files:
        return "not set in loaded .env files"
    return "no .env file found"


GEMINI_API_KEY_SOURCE = _load_env()


class Settings(BaseSettings):
    """All MITRA configuration values loaded from environment / .env file."""

    model_config = SettingsConfigDict(
        env_file=tuple(str(path) for path in ENV_FILES if path.exists()),
        env_file_encoding="utf-8",
    )

    # Gemini
    gemini_api_key: str = ""

    # Server
    jarvis_host: str = "0.0.0.0"
    jarvis_port: int = 8001

    # Database
    database_url: str = "jarvis.db"

    # Logging
    log_level: str = "INFO"

    # Speech
    microphone_index: int = 2
    tts_rate: int = 175
    tts_volume: float = 1.0

    # ElevenLabs TTS
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "auq43ws1oslv0tO4BDa7"

    # Wake word
    wake_word_enabled: bool = True
    wake_word: str = "mitra"


# Singleton instance used throughout the application
settings = Settings()

print(
    "MITRA config: GEMINI_API_KEY "
    f"{'loaded' if os.getenv('GEMINI_API_KEY') else 'missing'} "
    f"(source: {GEMINI_API_KEY_SOURCE})"
)
