"""Screenshot manager — capture the screen and save to memory/screenshots/.

Screenshots are saved with an ISO-8601 timestamp so they never overwrite
each other and can be found chronologically.

Primary backend: ``pyautogui.screenshot()`` (uses Pillow under the hood).
Fallback: macOS ``screencapture`` CLI (ships with every macOS install).
"""

from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path

from backend.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Screenshots directory
# The spec requires saving inside the project's memory/screenshots folder.
# Resolve relative to the repo root (two levels above jarvis/backend/system/).
# ---------------------------------------------------------------------------
_SCREENSHOTS_DIR = (
    Path(__file__).resolve().parent   # jarvis/backend/system
    .parent                            # jarvis/backend
    .parent                            # jarvis
    .parent                            # AI_ASSISTANT  (project root)
    / "memory"
    / "screenshots"
)

# ---------------------------------------------------------------------------
# Detect available backend
# ---------------------------------------------------------------------------
try:
    import pyautogui as _pyautogui
    _PYAUTOGUI_AVAILABLE = True
except ImportError:
    _PYAUTOGUI_AVAILABLE = False
    logger.warning("pyautogui not installed — falling back to macOS screencapture.")


def _ensure_dir() -> Path:
    """Create the screenshots directory if it does not exist."""
    _SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    return _SCREENSHOTS_DIR


def _timestamped_path(suffix: str = ".png") -> Path:
    """Return a unique file path with an ISO-8601 timestamp."""
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return _ensure_dir() / f"screenshot_{ts}{suffix}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def take_screenshot() -> str:
    """Capture the full screen and save it to the screenshots directory.

    Returns:
        Natural-language status string including the saved file path.
    """
    save_path = _timestamped_path(".png")

    # --- Primary: pyautogui ---
    if _PYAUTOGUI_AVAILABLE:
        try:
            import pyautogui
            screenshot = pyautogui.screenshot()
            screenshot.save(str(save_path))
            logger.info("Screenshot saved via pyautogui: %s", save_path)
            return (
                f"Screenshot captured and saved to "
                f"{save_path.name}, Sir."
            )
        except Exception as exc:
            logger.warning("pyautogui screenshot failed, trying screencapture: %s", exc)

    # --- Fallback: macOS screencapture ---
    try:
        result = subprocess.run(
            ["screencapture", "-x", str(save_path)],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and save_path.exists():
            logger.info("Screenshot saved via screencapture: %s", save_path)
            return (
                f"Screenshot captured and saved to "
                f"{save_path.name}, Sir."
            )
        err = result.stderr.strip() or "screencapture returned a non-zero exit code."
        logger.error("screencapture failed: %s", err)
        return f"Screenshot failed: {err}"
    except FileNotFoundError:
        return "Screenshot capture is only supported on macOS."
    except subprocess.TimeoutExpired:
        return "Screenshot timed out."
    except Exception as exc:
        logger.error("take_screenshot unexpected error: %s", exc)
        return f"Screenshot failed: {exc}"


def list_screenshots() -> str:
    """Return a list of existing screenshots in the screenshots directory.

    Returns:
        Natural-language summary string.
    """
    try:
        d = _ensure_dir()
        files = sorted(d.glob("*.png"), reverse=True)
        if not files:
            return "No screenshots found in the memory folder."
        names = [f.name for f in files[:10]]
        total = len(files)
        summary = ", ".join(names[:5])
        if total > 5:
            summary += f" and {total - 5} more"
        return f"Found {total} screenshot(s). Most recent: {summary}."
    except Exception as exc:
        logger.error("list_screenshots error: %s", exc)
        return f"Could not list screenshots: {exc}"
