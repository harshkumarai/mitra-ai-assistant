"""Application controller — open and close macOS applications.

All operations use the macOS ``open -a`` command and AppleScript ``quit``.
No shell-injection risk: application names are passed as list arguments,
never concatenated into a shell string.
"""

from __future__ import annotations

import subprocess
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Canonical name aliases
# Maps common spoken names → exact .app bundle names in /Applications
# ---------------------------------------------------------------------------
_APP_ALIASES: dict[str, str] = {
    # Browsers
    "chrome": "Google Chrome",
    "google chrome": "Google Chrome",
    "firefox": "Firefox",
    "safari": "Safari",
    "edge": "Microsoft Edge",
    "brave": "Brave Browser",
    "opera": "Opera",
    # Editors / IDEs
    "vscode": "Visual Studio Code",
    "vs code": "Visual Studio Code",
    "visual studio code": "Visual Studio Code",
    "code": "Visual Studio Code",
    "sublime": "Sublime Text",
    "sublime text": "Sublime Text",
    "atom": "Atom",
    "xcode": "Xcode",
    "pycharm": "PyCharm",
    "intellij": "IntelliJ IDEA",
    "cursor": "Cursor",
    # Music / media
    "spotify": "Spotify",
    "music": "Music",
    "apple music": "Music",
    "vlc": "VLC",
    "youtube music": "YouTube Music",
    # Communication
    "slack": "Slack",
    "discord": "Discord",
    "zoom": "zoom.us",
    "teams": "Microsoft Teams",
    "whatsapp": "WhatsApp",
    "telegram": "Telegram",
    "messages": "Messages",
    "facetime": "FaceTime",
    # Productivity
    "notion": "Notion",
    "obsidian": "Obsidian",
    "notes": "Notes",
    "calendar": "Calendar",
    "reminders": "Reminders",
    "mail": "Mail",
    "word": "Microsoft Word",
    "excel": "Microsoft Excel",
    "powerpoint": "Microsoft PowerPoint",
    "pages": "Pages",
    "numbers": "Numbers",
    "keynote": "Keynote",
    # System
    "finder": "Finder",
    "terminal": "Terminal",
    "iterm": "iTerm",
    "iterm2": "iTerm",
    "activity monitor": "Activity Monitor",
    "system preferences": "System Preferences",
    "system settings": "System Preferences",
    "calculator": "Calculator",
    "preview": "Preview",
    "photos": "Photos",
    # AI tools
    "chatgpt": "ChatGPT",
    "claude": "Claude",
}


def _resolve_app_name(raw: str) -> str:
    """Return the canonical app bundle name for *raw* spoken input."""
    return _APP_ALIASES.get(raw.strip().lower(), raw.strip())


def open_application(name: str) -> str:
    """Launch a macOS application by name.

    Uses ``open -a <name>`` which is safe (no shell expansion) and
    idempotent (re-opens / focuses an already running app).

    Args:
        name: Spoken or typed application name (e.g. ``"vs code"``).

    Returns:
        Natural-language status string.
    """
    app_name = _resolve_app_name(name)
    try:
        subprocess.run(
            ["open", "-a", app_name],
            check=True,
            capture_output=True,
            timeout=10,
        )
        logger.info("Opened application: %r", app_name)
        return f"Certainly, Sir. Opening {app_name}."
    except subprocess.CalledProcessError:
        logger.warning("Application not found: %r", app_name)
        return (
            f"I couldn't find an application called {app_name!r}. "
            "Please check the name or ensure it is installed."
        )
    except FileNotFoundError:
        logger.error("macOS 'open' command not available.")
        return "Application launching is only supported on macOS."
    except subprocess.TimeoutExpired:
        logger.warning("open -a timed out for %r", app_name)
        return f"Timed out while trying to open {app_name}."
    except Exception as exc:
        logger.error("open_application unexpected error: %s", exc)
        return f"Failed to open {app_name!r}: {exc}"


def close_application(name: str) -> str:
    """Quit a running macOS application using AppleScript.

    Uses ``tell application <name> to quit`` which asks the app to quit
    gracefully (same as Cmd+Q).

    Args:
        name: Spoken or typed application name.

    Returns:
        Natural-language status string.
    """
    app_name = _resolve_app_name(name)
    script = f'tell application "{app_name}" to quit'
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=8,
        )
        if result.returncode == 0:
            logger.info("Closed application: %r", app_name)
            return f"Closing {app_name}, Sir."
        # AppleScript returns non-zero if the app is not running — treat as info
        stderr = result.stderr.strip()
        if "not running" in stderr.lower() or "-1728" in stderr:
            logger.info("App not running: %r", app_name)
            return f"{app_name} is not currently running."
        logger.warning("close_application AppleScript error for %r: %s", app_name, stderr)
        return f"Could not close {app_name}: {stderr or 'Unknown error.'}"
    except FileNotFoundError:
        return "Application control via AppleScript is only supported on macOS."
    except subprocess.TimeoutExpired:
        return f"Timed out while trying to close {app_name}."
    except Exception as exc:
        logger.error("close_application unexpected error: %s", exc)
        return f"Failed to close {app_name!r}: {exc}"


def list_running_apps() -> str:
    """Return a comma-separated list of currently running GUI apps.

    Returns:
        Natural-language string listing running applications.
    """
    script = (
        'tell application "System Events" to get name of every process '
        "where background only is false"
    )
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=8,
        )
        if result.returncode == 0:
            apps = [a.strip() for a in result.stdout.strip().split(",") if a.strip()]
            return "Currently running applications: " + ", ".join(apps) + "."
        return "Could not retrieve the list of running applications."
    except Exception as exc:
        logger.error("list_running_apps error: %s", exc)
        return f"Failed to list running apps: {exc}"
