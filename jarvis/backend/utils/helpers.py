"""Shared utility functions used across the MITRA backend."""

import uuid
from pathlib import Path

# Directories that file operations are permitted to access
_ALLOWED_ROOTS: list[Path] = [
    Path.home(),
    Path("/tmp"),
]


def sanitize_path(path: str) -> Path:
    """Resolve *path* and verify it stays within an allowed directory.

    Args:
        path: Raw path string from user input.

    Returns:
        A fully resolved :class:`pathlib.Path`.

    Raises:
        ValueError: If the resolved path escapes all allowed root directories.
    """
    resolved = Path(path).expanduser().resolve()
    for root in _ALLOWED_ROOTS:
        try:
            resolved.relative_to(root.resolve())
            return resolved
        except ValueError:
            continue
    raise ValueError(
        f"Path '{resolved}' is outside the allowed directories: "
        + ", ".join(str(r) for r in _ALLOWED_ROOTS)
    )


def format_bytes(num_bytes: int) -> str:
    """Return a human-readable representation of *num_bytes*.

    Args:
        num_bytes: Raw byte count.

    Returns:
        String such as ``'1.23 MB'``.
    """
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:.2f} {unit}"
        num_bytes /= 1024.0  # type: ignore[assignment]
    return f"{num_bytes:.2f} PB"


def truncate_text(text: str, max_len: int = 200) -> str:
    """Truncate *text* to at most *max_len* characters, appending ``'…'``.

    Args:
        text: The original string.
        max_len: Maximum allowed length (default 200).

    Returns:
        Truncated (or unchanged) string.
    """
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def generate_session_id() -> str:
    """Generate a random UUID4 hex string suitable for session IDs.

    Returns:
        32-character hex string with no hyphens.
    """
    return uuid.uuid4().hex
