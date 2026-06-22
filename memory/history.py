"""
memory/history.py
-----------------
Long-term persistent command history stored as a JSON file.

Every interaction (user input + assistant response + timestamp) is appended
to the history file so the user can review past commands and the assistant
can optionally surface relevant history in future sessions.

The file path is configured via HISTORY_FILE_PATH in config.py.
"""

import json
import os
import datetime
from utilities.logger import get_logger
import config

logger = get_logger(__name__)


class CommandHistory:
    """
    Appends every command/response pair to a JSON file on disk.

    File format — a JSON array of objects:
    [
        {
            "timestamp": "2025-06-09T14:32:00",
            "user_input": "what time is it",
            "response": "The current time is 02:32 PM."
        },
        ...
    ]
    """

    def __init__(self):
        self._path = config.HISTORY_FILE_PATH
        self._ensure_file()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(self, user_input: str, response: str) -> None:
        """
        Append a new entry to the history file.

        Parameters
        ----------
        user_input : str
            Transcribed user command.
        response : str
            Assistant's spoken reply.
        """
        entry = {
            "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
            "user_input": user_input,
            "response": response,
        }
        records = self._load()
        records.append(entry)
        self._write(records)
        logger.debug("History saved: %s", entry["timestamp"])

    def load_all(self) -> list[dict]:
        """Return the full history as a list of dicts."""
        return self._load()

    def recent(self, n: int = 10) -> list[dict]:
        """Return the `n` most recent history entries."""
        return self._load()[-n:]

    def clear(self) -> None:
        """Delete all history entries (irreversible)."""
        self._write([])
        logger.info("Command history cleared.")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _ensure_file(self) -> None:
        """Create the history file (and parent directories) if needed."""
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        if not os.path.exists(self._path):
            self._write([])

    def _load(self) -> list[dict]:
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Could not load history: %s", exc)
            return []

    def _write(self, records: list[dict]) -> None:
        try:
            with open(self._path, "w", encoding="utf-8") as fh:
                json.dump(records, fh, indent=2, ensure_ascii=False)
        except OSError as exc:
            logger.error("Could not write history: %s", exc)
