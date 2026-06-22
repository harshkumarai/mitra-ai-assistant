"""File and folder manager — open folders, create folders, search for files.

SAFETY RULES enforced in this module:
  - No file deletion.
  - No arbitrary shell command execution from user input.
  - Path operations are restricted to the user's home directory and /tmp.
  - Folder creation is restricted to the user's Desktop and home directory.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from backend.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Allowed roots for file search and folder creation
# ---------------------------------------------------------------------------
_HOME = Path.home()
_ALLOWED_SEARCH_ROOTS: list[Path] = [_HOME, Path("/tmp")]
_MAX_SEARCH_RESULTS = 50

# ---------------------------------------------------------------------------
# Common folder shortcuts
# ---------------------------------------------------------------------------
_FOLDER_SHORTCUTS: dict[str, Path] = {
    "downloads": _HOME / "Downloads",
    "desktop": _HOME / "Desktop",
    "documents": _HOME / "Documents",
    "pictures": _HOME / "Pictures",
    "music": _HOME / "Music",
    "movies": _HOME / "Movies",
    "applications": Path("/Applications"),
    "home": _HOME,
    "icloud": _HOME / "Library" / "Mobile Documents" / "com~apple~CloudDocs",
}


def _safe_path(raw: str) -> Path:
    """Resolve *raw* and verify it is inside an allowed root.

    Args:
        raw: Path string from user input.

    Returns:
        Resolved :class:`pathlib.Path`.

    Raises:
        ValueError: If the path escapes all allowed roots.
    """
    resolved = Path(raw).expanduser().resolve()
    for root in _ALLOWED_SEARCH_ROOTS + [Path("/Applications")]:
        try:
            resolved.relative_to(root.resolve())
            return resolved
        except ValueError:
            continue
    raise ValueError(
        f"Path '{resolved}' is outside allowed directories."
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def open_folder(name: str) -> str:
    """Open a named folder in Finder.

    Accepts shortcut names (``'downloads'``, ``'desktop'``) or absolute paths.

    Args:
        name: Folder shortcut name or absolute path string.

    Returns:
        Natural-language status string.
    """
    # Check shortcuts first
    folder = _FOLDER_SHORTCUTS.get(name.strip().lower())

    if folder is None:
        # Try to resolve as a literal path
        try:
            folder = _safe_path(name)
        except ValueError as exc:
            return str(exc)

    if not folder.exists():
        return f"The folder '{folder}' does not exist on this system."

    try:
        subprocess.run(
            ["open", str(folder)],
            check=True,
            capture_output=True,
            timeout=8,
        )
        logger.info("Opened folder: %s", folder)
        return f"Opening {folder.name} in Finder, Sir."
    except subprocess.CalledProcessError as exc:
        logger.error("open_folder CalledProcessError: %s", exc)
        return f"Could not open folder '{folder.name}'."
    except Exception as exc:
        logger.error("open_folder error: %s", exc)
        return f"Failed to open folder: {exc}"


def create_folder(name: str, parent: str = "~/Desktop") -> str:
    """Create a new folder on the Desktop (or *parent* if specified).

    Args:
        name: Name for the new folder (must not contain path separators).
        parent: Parent directory path (default: ``~/Desktop``).

    Returns:
        Natural-language status string.
    """
    # Sanitise: reject names that contain path separators or traversal sequences.
    raw_name = name.strip()
    if "/" in raw_name or "\\" in raw_name or ".." in raw_name:
        return "Invalid folder name: path separators are not allowed."
    safe_name = Path(raw_name).name
    if not safe_name:
        return "Please provide a valid folder name."

    try:
        parent_path = Path(parent).expanduser().resolve()
    except Exception:
        parent_path = _HOME / "Desktop"

    # Restrict to home or Desktop
    try:
        parent_path.relative_to(_HOME)
    except ValueError:
        return "Folder creation is only allowed within your home directory."

    new_folder = parent_path / safe_name

    try:
        new_folder.mkdir(parents=False, exist_ok=False)
        logger.info("Created folder: %s", new_folder)
        return f"Folder '{safe_name}' created on the Desktop, Sir."
    except FileExistsError:
        return f"A folder named '{safe_name}' already exists."
    except FileNotFoundError:
        return f"Parent directory '{parent_path}' does not exist."
    except PermissionError:
        return f"Permission denied: cannot create '{safe_name}'."
    except Exception as exc:
        logger.error("create_folder error: %s", exc)
        return f"Failed to create folder: {exc}"


def search_files(query: str, search_path: str = "~") -> str:
    """Search for files whose names contain *query* under *search_path*.

    Args:
        query: Substring to match against file names (case-insensitive).
        search_path: Root directory to search (default: home directory).

    Returns:
        Natural-language string listing matches.
    """
    if not query.strip():
        return "Please provide a search term."

    try:
        root = Path(search_path).expanduser().resolve()
        root.relative_to(_HOME)  # safety check
    except ValueError:
        return "File search is only allowed within your home directory."
    except Exception:
        root = _HOME

    if not root.exists():
        return f"The directory '{root}' does not exist."

    query_lower = query.strip().lower()
    matches: list[str] = []

    try:
        for dirpath, _dirs, files in os.walk(root):
            # Skip hidden directories to avoid long traversals
            _dirs[:] = [
                d for d in _dirs
                if not d.startswith(".")
                and d not in ("node_modules", "__pycache__", ".git")
            ]
            for fname in files:
                if query_lower in fname.lower():
                    matches.append(os.path.join(dirpath, fname))
                    if len(matches) >= _MAX_SEARCH_RESULTS:
                        break
            if len(matches) >= _MAX_SEARCH_RESULTS:
                break
    except PermissionError:
        pass  # Skip directories we can't read
    except Exception as exc:
        logger.error("search_files walk error: %s", exc)
        return f"Search encountered an error: {exc}"

    if not matches:
        return f"No files found matching '{query}'."

    display = [Path(m).name for m in matches[:10]]
    total = len(matches)
    summary = ", ".join(display[:5])
    if total > 5:
        summary += f" … and {total - 5} more"
    logger.info("Found %d file(s) for query %r", total, query)
    return f"Found {total} file(s) matching '{query}': {summary}."


def get_folder_path(name: str) -> str:
    """Return the full absolute path for a folder shortcut.

    Args:
        name: Shortcut name (e.g. ``'downloads'``).

    Returns:
        Path string or error message.
    """
    folder = _FOLDER_SHORTCUTS.get(name.strip().lower())
    if folder is None:
        return f"Unknown folder shortcut: '{name}'."
    return str(folder)
