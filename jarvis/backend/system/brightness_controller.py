"""Brightness controller for macOS.

Primary method: ``screen_brightness_control`` (cross-monitor, accurate).
Fallback method: AppleScript brightness key-code simulation (F1/F2) when
the primary method is unavailable.

Both paths are gracefully handled so the server never crashes on import.
"""

from __future__ import annotations

import subprocess
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Detect available backend
# ---------------------------------------------------------------------------
try:
    import screen_brightness_control as _sbc
    # Quick sanity check — the library has a known issue on some macOS/Python
    # combinations where the internal OS module is missing.
    _sbc.list_monitors()
    _SBC_AVAILABLE = True
    logger.info("screen_brightness_control backend available.")
except Exception:
    _SBC_AVAILABLE = False
    logger.info(
        "screen_brightness_control unavailable — using AppleScript key-code fallback."
    )

# Relative step size when no level is specified
_STEP_PERCENT = 10
# Number of key-presses per _STEP_PERCENT (each key adjusts ~6.25%)
_KEYS_PER_STEP = max(1, round(_STEP_PERCENT / 6.25))


# ---------------------------------------------------------------------------
# AppleScript key-code helpers
# ---------------------------------------------------------------------------

def _brightness_keys(key_code: int, count: int) -> tuple[int, str]:
    """Send *count* brightness key presses via AppleScript.

    Key codes:
      144 = F2 / Brightness Up
      145 = F1 / Brightness Down

    Args:
        key_code: macOS key code for the desired direction.
        count: Number of key presses to simulate.

    Returns:
        ``(returncode, stderr)`` tuple.
    """
    presses = "\n".join(f"    key code {key_code}" for _ in range(count))
    script = f'tell application "System Events"\n{presses}\nend tell'
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=8,
    )
    return result.returncode, result.stderr.strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_brightness() -> int:
    """Return the current display brightness (0–100).

    Returns:
        Integer brightness level, or -1 if undetectable.
    """
    if _SBC_AVAILABLE:
        try:
            import screen_brightness_control as sbc
            values = sbc.get_brightness()
            if values:
                level = values[0] if isinstance(values, list) else values
                return int(level)
        except Exception as exc:
            logger.debug("sbc.get_brightness failed: %s", exc)
    return -1  # fallback can't read current level


def set_brightness(level: int) -> str:
    """Set display brightness to an exact percentage.

    Args:
        level: Target brightness 0–100.

    Returns:
        Natural-language status string.
    """
    level = max(0, min(100, int(level)))

    if _SBC_AVAILABLE:
        try:
            import screen_brightness_control as sbc
            sbc.set_brightness(level)
            logger.info("Brightness set to %d%%", level)
            return f"Display brightness set to {level}%, Sir."
        except Exception as exc:
            logger.warning("sbc.set_brightness failed, using key fallback: %s", exc)

    # Key-code fallback: calculate steps from 0
    # Reset to minimum (20 key presses down), then step up
    try:
        _brightness_keys(145, 20)  # go to minimum
        steps_up = round(level / 6.25)
        if steps_up > 0:
            rc, err = _brightness_keys(144, steps_up)
            if rc != 0:
                return f"Could not set brightness: {err or 'Unknown error.'}"
        logger.info("Brightness set via key simulation to ~%d%%", level)
        return f"Display brightness set to approximately {level}%, Sir."
    except FileNotFoundError:
        return "Brightness control is only supported on macOS."
    except Exception as exc:
        logger.error("set_brightness key fallback error: %s", exc)
        return f"Failed to set brightness: {exc}"


def increase_brightness(step: int = _STEP_PERCENT) -> str:
    """Increase display brightness by *step* percent.

    Args:
        step: Percentage points to increase (default 10).

    Returns:
        Natural-language status string.
    """
    if _SBC_AVAILABLE:
        try:
            import screen_brightness_control as sbc
            current_list = sbc.get_brightness()
            current = current_list[0] if isinstance(current_list, list) else current_list
            new_level = min(100, int(current) + step)
            sbc.set_brightness(new_level)
            logger.info("Brightness increased: %d -> %d", current, new_level)
            return f"Brightness increased to {new_level}%, Sir."
        except Exception as exc:
            logger.warning("sbc increase failed, using key fallback: %s", exc)

    # Key-code fallback
    key_count = max(1, round(step / 6.25))
    try:
        rc, err = _brightness_keys(144, key_count)
        if rc == 0:
            logger.info("Brightness increased by %d key(s).", key_count)
            return "Brightness increased, Sir."
        return f"Could not increase brightness: {err or 'Unknown error.'}"
    except FileNotFoundError:
        return "Brightness control is only supported on macOS."
    except Exception as exc:
        logger.error("increase_brightness error: %s", exc)
        return f"Failed to increase brightness: {exc}"


def decrease_brightness(step: int = _STEP_PERCENT) -> str:
    """Decrease display brightness by *step* percent.

    Args:
        step: Percentage points to decrease (default 10).

    Returns:
        Natural-language status string.
    """
    if _SBC_AVAILABLE:
        try:
            import screen_brightness_control as sbc
            current_list = sbc.get_brightness()
            current = current_list[0] if isinstance(current_list, list) else current_list
            new_level = max(0, int(current) - step)
            sbc.set_brightness(new_level)
            logger.info("Brightness decreased: %d -> %d", current, new_level)
            return f"Brightness decreased to {new_level}%, Sir."
        except Exception as exc:
            logger.warning("sbc decrease failed, using key fallback: %s", exc)

    key_count = max(1, round(step / 6.25))
    try:
        rc, err = _brightness_keys(145, key_count)
        if rc == 0:
            logger.info("Brightness decreased by %d key(s).", key_count)
            return "Brightness decreased, Sir."
        return f"Could not decrease brightness: {err or 'Unknown error.'}"
    except FileNotFoundError:
        return "Brightness control is only supported on macOS."
    except Exception as exc:
        logger.error("decrease_brightness error: %s", exc)
        return f"Failed to decrease brightness: {exc}"
