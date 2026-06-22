"""Structured logging setup with rotating file handler and coloured console output."""

import logging
import sys
from logging.handlers import RotatingFileHandler

from backend.config import settings

# ANSI colour codes for console output
_COLOURS = {
    "DEBUG": "\033[36m",    # Cyan
    "INFO": "\033[32m",     # Green
    "WARNING": "\033[33m",  # Yellow
    "ERROR": "\033[31m",    # Red
    "CRITICAL": "\033[35m", # Magenta
    "RESET": "\033[0m",
}


class _ColourFormatter(logging.Formatter):
    """Logging formatter that adds ANSI colours to the level name."""

    _FMT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    _DATE_FMT = "%Y-%m-%d %H:%M:%S"

    def format(self, record: logging.LogRecord) -> str:
        """Return a coloured, formatted log line."""
        colour = _COLOURS.get(record.levelname, _COLOURS["RESET"])
        reset = _COLOURS["RESET"]
        record.levelname = f"{colour}{record.levelname}{reset}"
        formatter = logging.Formatter(self._FMT, datefmt=self._DATE_FMT)
        return formatter.format(record)


def get_logger(name: str) -> logging.Logger:
    """Return a logger with rotating file + coloured console handlers.

    Args:
        name: The logger name, typically ``__name__``.

    Returns:
        A configured :class:`logging.Logger` instance.
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logger.setLevel(level)

    # Rotating file handler — 5 MB x 3 backups
    file_handler = RotatingFileHandler(
        "mitra.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    plain_fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(plain_fmt)

    # Coloured console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(_ColourFormatter())

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.propagate = False

    return logger
