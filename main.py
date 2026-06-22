"""
main.py
-------
Entry point for the voice assistant application.
Run this file to start the assistant:

    python main.py

Any top-level bootstrapping (env checks, dependency validation) belongs here
so the rest of the codebase stays clean.
"""

import sys
from utilities.logger import get_logger
from assistant import VoiceAssistant

logger = get_logger(__name__)


def check_dependencies() -> bool:
    """Verify that required dependencies are importable. pyaudio is optional (text mode fallback)."""
    missing = []
    for pkg in ("speech_recognition", "elevenlabs", "pygame"):
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)

    if missing:
        logger.error("Missing dependencies: %s", ", ".join(missing))
        print(
            f"[ERROR] Please install missing packages:\n"
            f"  pip install {' '.join(missing)}"
        )
        return False

    # pyaudio is optional — text mode activates automatically without it
    try:
        import pyaudio  # noqa: F401
    except ImportError:
        print(
            "[INFO] pyaudio not found — running in TEXT MODE (keyboard input).\n"
            "[INFO] To enable full voice: brew install portaudio && pip install pyaudio\n"
        )
    return True


def main():
    if not check_dependencies():
        sys.exit(1)

    assistant = VoiceAssistant()
    assistant.run()


if __name__ == "__main__":
    main()
