"""
utilities/logger.py
-------------------
Centralised logging configuration for the entire project.
Every module should obtain its logger via:

    from utilities.logger import get_logger
    logger = get_logger(__name__)

This ensures:
  - A consistent format across all modules.
  - Logs are written to both the console and a rotating file.
  - The log level is controlled from config.py (LOG_LEVEL).
"""

import logging
import logging.handlers
import config

# Track whether the root logger has been configured already
_configured = False


def _configure_root_logger() -> None:
    """One-time setup: attach handlers to the root logger."""
    global _configured  # noqa: PLW0603
    if _configured:
        return

    level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler — always INFO or above
    console_handler = logging.StreamHandler()
    console_handler.setLevel(max(level, logging.INFO))
    console_handler.setFormatter(formatter)

    # Rotating file handler — respects configured LOG_LEVEL, max 5 MB × 3 files
    file_handler = logging.handlers.RotatingFileHandler(
        config.LOG_FILE_PATH,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(console_handler)
    root.addHandler(file_handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger.  Configures the root logger on first call.

    Parameters
    ----------
    name : str
        Typically `__name__` from the calling module.

    Returns
    -------
    logging.Logger
    """
    _configure_root_logger()
    return logging.getLogger(name)
