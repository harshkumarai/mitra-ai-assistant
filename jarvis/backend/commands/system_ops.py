"""System-level command handlers: open apps, URLs, volume, time, battery."""

import subprocess
import webbrowser
from datetime import datetime

import psutil

from backend.utils.logger import get_logger

logger = get_logger(__name__)

APP_ALIASES = {
    "chrome": "Google Chrome",
    "google chrome": "Google Chrome",
}


def open_application(name: str) -> str:
    """Launch a macOS application by name using ``open -a``.

    Args:
        name: Application name as it appears in /Applications (e.g. ``'Safari'``).

    Returns:
        A status string describing the outcome.
    """
    app_name = APP_ALIASES.get(name.lower(), name)
    try:
        subprocess.run(["open", "-a", app_name], check=True, capture_output=True)  # noqa: S603
        logger.info("Opening application via macOS: open -a %r", app_name)
        return f"Opening {app_name}."
    except FileNotFoundError:
        logger.error("macOS open command is unavailable; cannot open: %s", app_name)
        return "Application launching is only supported on macOS."
    except subprocess.CalledProcessError:
        logger.warning("Application not found: %s", app_name)
        return f"I couldn't find an application called {app_name}."
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("open_application error: %s", exc)
        return f"Failed to open '{app_name}': {exc}"


def open_website(url: str) -> str:
    """Open *url* in the system default browser.

    Args:
        url: Full URL string (e.g. ``'https://google.com'``).

    Returns:
        A status string describing the outcome.
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        webbrowser.open(url)
        logger.info("Opened URL: %s", url)
        return f"Opening {url} in your browser."
    except Exception as exc:  # pylint: disable=broad-except
        logger.error("open_website error: %s", exc)
        return f"Failed to open URL: {exc}"


def get_battery_status() -> str:
    """Return a human-readable battery status string.

    Returns:
        Battery percentage and charging state, or a message if unavailable.
    """
    battery = psutil.sensors_battery()
    if battery is None:
        return "Battery information is not available on this device."
    plugged = "plugged in" if battery.power_plugged else "on battery"
    return f"Battery is at {battery.percent:.0f}% and {plugged}."


def get_system_time() -> str:
    """Return the current local date and time as a formatted string.

    Returns:
        Human-readable datetime string.
    """
    now = datetime.now().strftime("%A, %d %B %Y — %H:%M:%S")
    return f"The current time is {now}."


def set_volume(level: int) -> str:
    """Set the system output volume on macOS using AppleScript.

    Args:
        level: Volume level from 0 to 100.

    Returns:
        A status string describing the outcome.
    """
    level = max(0, min(100, level))
    applescript_level = int(level / 10)  # AppleScript uses 0–10 scale
    script = f"set volume output volume {level}"
    try:
        subprocess.run(  # noqa: S603
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
        )
        logger.info("Volume set to %d%%", level)
        return f"Volume set to {level}%."
    except FileNotFoundError:
        return "Volume control via AppleScript is only supported on macOS."
    except subprocess.CalledProcessError as exc:
        logger.error("set_volume AppleScript error: %s", exc)
        return f"Failed to set volume: {exc.stderr.decode().strip()}"
