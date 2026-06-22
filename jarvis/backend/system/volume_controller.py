"""Volume controller — get, set, increase, decrease, and mute system audio on macOS.

All volume operations use ``osascript`` (AppleScript), which is the standard,
safe, and dependency-free approach on macOS. No external packages required.
"""

from __future__ import annotations

import subprocess
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Step size for relative adjustments (percent)
_STEP = 10


def _run_applescript(script: str) -> tuple[int, str, str]:
    """Run an AppleScript expression and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=6,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def get_volume() -> int:
    """Return the current output volume level (0–100).

    Returns:
        Integer volume level, or -1 on error.
    """
    try:
        code, out, err = _run_applescript(
            "output volume of (get volume settings)"
        )
        if code == 0 and out.isdigit():
            return int(out)
        logger.error("get_volume error: %s", err)
        return -1
    except Exception as exc:
        logger.error("get_volume exception: %s", exc)
        return -1


def set_volume(level: int) -> str:
    """Set the system output volume to an exact level.

    Args:
        level: Volume level 0–100.

    Returns:
        Natural-language status string.
    """
    level = max(0, min(100, int(level)))
    try:
        code, _, err = _run_applescript(f"set volume output volume {level}")
        if code == 0:
            logger.info("Volume set to %d%%", level)
            return f"Volume set to {level}%, Sir."
        logger.error("set_volume AppleScript error: %s", err)
        return f"Could not set volume: {err or 'Unknown error.'}"
    except FileNotFoundError:
        return "Volume control is only supported on macOS."
    except Exception as exc:
        logger.error("set_volume exception: %s", exc)
        return f"Failed to set volume: {exc}"


def increase_volume(step: int = _STEP) -> str:
    """Increase output volume by *step* percent.

    Args:
        step: Percentage points to add (default 10).

    Returns:
        Natural-language status string.
    """
    current = get_volume()
    if current < 0:
        return "Could not read current volume level."
    new_level = min(100, current + step)
    result = set_volume(new_level)
    logger.info("Volume increased: %d -> %d", current, new_level)
    return f"Volume increased to {new_level}%, Sir."


def decrease_volume(step: int = _STEP) -> str:
    """Decrease output volume by *step* percent.

    Args:
        step: Percentage points to subtract (default 10).

    Returns:
        Natural-language status string.
    """
    current = get_volume()
    if current < 0:
        return "Could not read current volume level."
    new_level = max(0, current - step)
    result = set_volume(new_level)
    logger.info("Volume decreased: %d -> %d", current, new_level)
    return f"Volume decreased to {new_level}%, Sir."


def mute_audio() -> str:
    """Mute the system audio output.

    Returns:
        Natural-language status string.
    """
    try:
        code, _, err = _run_applescript("set volume output muted true")
        if code == 0:
            logger.info("Audio muted.")
            return "Audio muted, Sir."
        logger.error("mute_audio error: %s", err)
        return f"Could not mute audio: {err or 'Unknown error.'}"
    except FileNotFoundError:
        return "Audio mute is only supported on macOS."
    except Exception as exc:
        logger.error("mute_audio exception: %s", exc)
        return f"Failed to mute audio: {exc}"


def unmute_audio() -> str:
    """Unmute the system audio output.

    Returns:
        Natural-language status string.
    """
    try:
        code, _, err = _run_applescript("set volume output muted false")
        if code == 0:
            logger.info("Audio unmuted.")
            return "Audio unmuted, Sir."
        logger.error("unmute_audio error: %s", err)
        return f"Could not unmute audio: {err or 'Unknown error.'}"
    except FileNotFoundError:
        return "Audio unmute is only supported on macOS."
    except Exception as exc:
        logger.error("unmute_audio exception: %s", exc)
        return f"Failed to unmute audio: {exc}"
