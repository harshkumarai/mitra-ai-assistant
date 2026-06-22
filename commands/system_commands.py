"""
commands/system_commands.py
---------------------------
Handles operating-system level commands:
  - Opening applications  ("open Safari", "launch VS Code")
  - System actions        ("shutdown", "restart", "lock screen")
  - Volume control        ("volume up", "mute")

Uses Python's `subprocess` and `os` modules so it stays cross-platform
where possible, with macOS-specific fallbacks noted inline.
"""

import os
import subprocess
from commands.base_command import BaseCommand
from utilities.logger import get_logger

logger = get_logger(__name__)


class SystemCommand(BaseCommand):
    """Executes OS-level operations requested by the user."""

    _APP_ALIASES = {
        "chrome": "Google Chrome",
        "google chrome": "Google Chrome",
    }

    # Map spoken words to shell commands (macOS defaults shown).
    # Extend or override entries in config.py for other platforms.
    _ACTION_MAP = {
        "shutdown": "sudo shutdown -h now",
        "restart": "sudo shutdown -r now",
        "lock": "pmset displaysleepnow",         # macOS screen lock
        "mute": "osascript -e 'set volume output muted true'",
        "unmute": "osascript -e 'set volume output muted false'",
        "volume up": "osascript -e 'set volume output volume ((output volume of (get volume settings)) + 10)'",
        "volume down": "osascript -e 'set volume output volume ((output volume of (get volume settings)) - 10)'",
    }

    def execute(self, text: str, context) -> str:
        lowered = text.lower()

        # --- Volume / system action keywords ---
        for keyword, command in self._ACTION_MAP.items():
            if keyword in lowered:
                return self._run(command, keyword)

        # --- Open / launch an application ---
        if any(kw in lowered for kw in ("open", "launch", "start")):
            app_name = self._extract_app_name(lowered)
            if app_name:
                return self._open_app(self._resolve_app_name(app_name))
            return "Which application would you like me to open?"

        return "I'm not sure which system action you want. Could you rephrase?"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _run(self, shell_command: str, label: str) -> str:
        """Run a shell command and return a spoken confirmation."""
        try:
            subprocess.run(shell_command, shell=True, check=True)
            logger.info("System command executed: %s", label)
            return f"Done. {label.capitalize()} executed."
        except subprocess.CalledProcessError as exc:
            logger.error("System command failed: %s | %s", label, exc)
            return f"Sorry, I couldn't execute {label}."

    def _open_app(self, app_name: str) -> str:
        """Open a macOS application by name using the `open` command."""
        try:
            subprocess.run(["open", "-a", app_name], check=True)
            logger.info("Opening application via macOS: open -a %r", app_name)
            return f"Opening {app_name}."
        except FileNotFoundError:
            logger.error("macOS open command is unavailable; cannot open: %s", app_name)
            return "Application launching is only supported on macOS."
        except subprocess.CalledProcessError:
            logger.warning("Application not found: %s", app_name)
            return f"I couldn't find an application called {app_name}."

    def _resolve_app_name(self, app_name: str) -> str:
        """Resolve spoken app aliases to their macOS application names."""
        return self._APP_ALIASES.get(app_name.lower(), app_name)

    @staticmethod
    def _extract_app_name(text: str) -> str:
        """
        Extract the application name that follows trigger words.
        E.g. "open safari please" → "safari"
        """
        for kw in ("open", "launch", "start"):
            if kw in text:
                # Take everything after the keyword and strip filler words
                after = text.split(kw, 1)[-1].strip()
                for filler in ("app", "application", "please", "the"):
                    after = after.replace(filler, "").strip()
                return after.title()
        return ""
