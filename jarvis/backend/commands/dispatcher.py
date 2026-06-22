"""Command dispatcher: routes text input to system or student operation handlers.

Routing priority (first match wins):
  1. Computer-control commands  → backend.system.*
  2. Legacy system commands     → backend.commands.system_ops
  3. Student productivity       → backend.commands.student_ops
  4. No match                   → return None (caller falls through to Gemini)
"""

import re

from backend.commands import student_ops, system_ops
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Lazy imports for system-control modules
# Each module is imported only when a match fires so server startup is fast
# and a missing optional dependency cannot prevent the server from starting.
# ---------------------------------------------------------------------------

def _app() -> object:
    from backend.system import app_controller
    return app_controller

def _vol() -> object:
    from backend.system import volume_controller
    return volume_controller

def _bright() -> object:
    from backend.system import brightness_controller
    return brightness_controller

def _ss() -> object:
    from backend.system import screenshot_manager
    return screenshot_manager

def _files() -> object:
    from backend.system import file_manager
    return file_manager


# ---------------------------------------------------------------------------
# Pattern tables
# Each entry: (compiled_regex, callable_factory, arg_extractor)
#
# callable_factory  — zero-arg callable that returns the actual handler
#                     function (supports lazy module loading).
# arg_extractor     — receives re.Match, returns positional args tuple.
# ---------------------------------------------------------------------------

# ── 1. Computer-control patterns (new) ────────────────────────────────────

_COMPUTER_CONTROL_PATTERNS: list[
    tuple[re.Pattern[str], object, object]
] = [

    # ── File: open folder shortcut ────────────────────────────────────────
    # MUST be before the generic "open <app>" pattern so "open downloads"
    # is routed to the file manager, not the app controller.
    # "open downloads" / "open my desktop" / "open documents folder"
    (
        re.compile(
            r"\bopen\s+(?:my\s+)?(?:the\s+)?"
            r"(downloads?|desktop|documents?|pictures?|music|movies?|applications?|home|icloud)"
            r"(?:\s+folder)?\b",
            re.IGNORECASE,
        ),
        lambda: _files().open_folder,
        lambda m: (m.group(1).rstrip("s").lower()
                   if m.group(1).lower() in ("downloads", "documents", "pictures", "movies")
                   else m.group(1).lower(),),
    ),

    # ── Application: open ────────────────────────────────────────────────
    # "open Chrome" / "launch Spotify" / "start VS Code"
    (
        re.compile(
            r"\b(?:open|launch|start|run)\s+(.+)",
            re.IGNORECASE,
        ),
        lambda: _app().open_application,
        lambda m: (m.group(1).strip(),),
    ),

    # ── Application: close / quit ────────────────────────────────────────
    # "close Chrome" / "quit Safari" / "kill Spotify"
    (
        re.compile(
            r"\b(?:close|quit|exit|kill)\s+(.+)",
            re.IGNORECASE,
        ),
        lambda: _app().close_application,
        lambda m: (m.group(1).strip(),),
    ),

    # ── Application: list running apps ───────────────────────────────────
    (
        re.compile(
            r"\b(?:list|show|what)\s+(?:running\s+)?(?:apps|applications|programs)\b",
            re.IGNORECASE,
        ),
        lambda: _app().list_running_apps,
        lambda m: (),
    ),

    # ── Volume: set exact level ───────────────────────────────────────────
    # "set volume to 70" / "volume 50"
    (
        re.compile(
            r"(?:set\s+)?volume\s+(?:to\s+)?(\d{1,3})(?:\s*%)?",
            re.IGNORECASE,
        ),
        lambda: _vol().set_volume,
        lambda m: (int(m.group(1)),),
    ),

    # ── Volume: increase ─────────────────────────────────────────────────
    # "increase volume" / "volume up" / "louder" / "turn up volume"
    (
        re.compile(
            r"\b(?:increase|raise|turn\s+up|crank\s+up|louder|higher)\s+(?:the\s+)?volume\b"
            r"|\bvolume\s+(?:up|higher|louder)\b",
            re.IGNORECASE,
        ),
        lambda: _vol().increase_volume,
        lambda m: (),
    ),

    # ── Volume: decrease ─────────────────────────────────────────────────
    # "decrease volume" / "volume down" / "quieter"
    (
        re.compile(
            r"\b(?:decrease|lower|turn\s+down|reduce|quieter|softer)\s+(?:the\s+)?volume\b"
            r"|\bvolume\s+(?:down|lower|quieter)\b",
            re.IGNORECASE,
        ),
        lambda: _vol().decrease_volume,
        lambda m: (),
    ),

    # ── Volume: mute ─────────────────────────────────────────────────────
    (
        re.compile(
            r"\b(?:mute|silence|shut\s+up|no\s+sound)\b(?:\s+(?:the\s+)?(?:audio|sound|volume))?",
            re.IGNORECASE,
        ),
        lambda: _vol().mute_audio,
        lambda m: (),
    ),

    # ── Volume: unmute ────────────────────────────────────────────────────
    (
        re.compile(
            r"\b(?:unmute|restore\s+sound|enable\s+audio)\b",
            re.IGNORECASE,
        ),
        lambda: _vol().unmute_audio,
        lambda m: (),
    ),

    # ── Brightness: set exact level ───────────────────────────────────────
    # "set brightness to 80" / "brightness 60%"
    (
        re.compile(
            r"(?:set\s+)?brightness\s+(?:to\s+)?(\d{1,3})(?:\s*%)?",
            re.IGNORECASE,
        ),
        lambda: _bright().set_brightness,
        lambda m: (int(m.group(1)),),
    ),

    # ── Brightness: increase ──────────────────────────────────────────────
    (
        re.compile(
            r"\b(?:increase|raise|turn\s+up|brighter|higher)\s+(?:the\s+)?brightness\b"
            r"|\bbrightness\s+(?:up|higher|brighter)\b",
            re.IGNORECASE,
        ),
        lambda: _bright().increase_brightness,
        lambda m: (),
    ),

    # ── Brightness: decrease ──────────────────────────────────────────────
    (
        re.compile(
            r"\b(?:decrease|lower|turn\s+down|dimmer|reduce)\s+(?:the\s+)?brightness\b"
            r"|\bbrightness\s+(?:down|lower|dimmer)\b",
            re.IGNORECASE,
        ),
        lambda: _bright().decrease_brightness,
        lambda m: (),
    ),

    # ── Screenshot ────────────────────────────────────────────────────────
    # "take a screenshot" / "capture screen" / "screenshot"
    (
        re.compile(
            r"\b(?:take\s+(?:a\s+)?screenshot|capture\s+(?:the\s+)?screen|screenshot)\b",
            re.IGNORECASE,
        ),
        lambda: _ss().take_screenshot,
        lambda m: (),
    ),

    # ── Screenshot: list ──────────────────────────────────────────────────
    (
        re.compile(
            r"\b(?:list|show)\s+(?:my\s+)?screenshots?\b",
            re.IGNORECASE,
        ),
        lambda: _ss().list_screenshots,
        lambda m: (),
    ),

    # ── File: create folder ───────────────────────────────────────────────
    # "create a folder named Projects" / "make a new folder called Work"
    (
        re.compile(
            r"\b(?:create|make|new)\s+(?:a\s+)?(?:new\s+)?folder\s+"
            r"(?:named?|called?|titled?)?\s*[\"']?(.+?)[\"']?\s*$",
            re.IGNORECASE,
        ),
        lambda: _files().create_folder,
        lambda m: (m.group(1).strip(),),
    ),

    # ── File: search ──────────────────────────────────────────────────────
    # "search for resume.pdf" / "find file budget" / "look for notes.txt"
    (
        re.compile(
            r"\b(?:search\s+for|find\s+file|find|look\s+for|locate)\s+[\"']?(.+?)[\"']?\s*$",
            re.IGNORECASE,
        ),
        lambda: _files().search_files,
        lambda m: (m.group(1).strip(),),
    ),
]


# ── 2. Legacy system patterns (unchanged) ─────────────────────────────────

_SYSTEM_PATTERNS: list[tuple[re.Pattern[str], object, object]] = [
    # "open chrome" / "launch chrome" / "start chrome"
    (
        re.compile(r"\b(?:open|launch|start)\s+(?:google\s+)?chrome\b", re.IGNORECASE),
        system_ops.open_application,
        lambda m: ("Google Chrome",),
    ),
    # "open app <name>" / "open application <name>"
    (
        re.compile(r"open (?:app|application)\s+(.+)", re.IGNORECASE),
        system_ops.open_application,
        lambda m: (m.group(1).strip(),),
    ),
    # "open website <url>" / "go to <url>" / "browse <url>"
    (
        re.compile(r"(?:open website|go to|browse)\s+([\S]+)", re.IGNORECASE),
        system_ops.open_website,
        lambda m: (m.group(1).strip(),),
    ),
    # "battery" / "battery status"
    (
        re.compile(r"\bbattery(?:\s+status)?\b", re.IGNORECASE),
        system_ops.get_battery_status,
        lambda m: (),
    ),
    # "what time is it" / "current time" / "time"
    (
        re.compile(r"\b(?:what(?:'s|\s+is)?\s+the\s+)?(?:current\s+)?time\b", re.IGNORECASE),
        system_ops.get_system_time,
        lambda m: (),
    ),
    # "set volume to <N>" / "volume <N>"
    (
        re.compile(r"(?:set\s+)?volume\s+(?:to\s+)?(\d{1,3})", re.IGNORECASE),
        system_ops.set_volume,
        lambda m: (int(m.group(1)),),
    ),
]


# ── 3. Natural-language reminder patterns (new) ──────────────────────────
# These are checked BEFORE the legacy student_ops pattern so phrases like
# "remind me in 10 minutes" are handled here rather than falling through.

_NL_REMINDER_TRIGGERS = re.compile(
    r"\b(?:remind(?:\s+me)?|set\s+(?:a\s+)?(?:reminder|alarm)|alarm\s+for)\b",
    re.IGNORECASE,
)


async def _nl_reminder_handler(text: str) -> str:
    """Parse a natural-language reminder utterance and save to DB.

    Args:
        text: Raw user input.

    Returns:
        Human-readable confirmation or error string.
    """
    from datetime import datetime
    from backend.database.connection import get_db
    from backend.utils.time_parser import extract_reminder_info

    title, remind_at = extract_reminder_info(text)

    if remind_at is None:
        return (
            "I couldn't figure out when to remind you, Harsh. "
            'Try something like "remind me in 10 minutes to call mom" '
            'or "set alarm for 7 PM".'
        )

    remind_at_str = remind_at.strftime("%Y-%m-%d %H:%M")

    try:
        async for db in get_db():
            cursor = await db.execute(
                "INSERT INTO reminders (title, remind_at) VALUES (?, ?)",
                (title, remind_at_str),
            )
            await db.commit()
            reminder_id = cursor.lastrowid

        # Human-friendly time display
        now = datetime.now()
        delta = remind_at - now
        total_seconds = int(delta.total_seconds())
        if total_seconds < 3600:
            human_time = f"in {total_seconds // 60} minute(s)"
        elif total_seconds < 86400:
            human_time = f"at {remind_at.strftime('%I:%M %p')}"
        else:
            human_time = f"on {remind_at.strftime('%A at %I:%M %p')}"

        logger.info("NL reminder saved: id=%s title=%r at=%s", reminder_id, title, remind_at_str)
        return f"Got it, Harsh. I'll remind you about '{title}' {human_time}."

    except Exception as exc:  # pylint: disable=broad-except
        logger.error("NL reminder handler error: %s", exc)
        return f"Sorry Harsh, I couldn't save that reminder: {exc}"


# ── 4. Student productivity patterns (unchanged) ──────────────────────────

_STUDENT_PATTERNS: list[tuple[re.Pattern[str], object, object]] = [
    # "add task <title> due <date>"
    (
        re.compile(r"add task\s+(.+?)\s+due\s+(\d{4}-\d{2}-\d{2})", re.IGNORECASE),
        student_ops.add_task,
        lambda m: (m.group(1).strip(), m.group(2).strip()),
    ),
    # "add task <title>"
    (
        re.compile(r"add task\s+(.+)", re.IGNORECASE),
        student_ops.add_task,
        lambda m: (m.group(1).strip(),),
    ),
    # "add note <title>: <content>"
    (
        re.compile(r"add note\s+(.+?):\s*(.+)", re.IGNORECASE),
        student_ops.add_note,
        lambda m: (m.group(1).strip(), m.group(2).strip()),
    ),
    # "add note <title>"
    (
        re.compile(r"add note\s+(.+)", re.IGNORECASE),
        student_ops.add_note,
        lambda m: (m.group(1).strip(),),
    ),
    # "remind me about <title> at <datetime>"
    (
        re.compile(
            r"remind(?:\s+me)?\s+(?:about\s+)?(.+?)\s+at\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})",
            re.IGNORECASE,
        ),
        student_ops.add_reminder,
        lambda m: (m.group(1).strip(), m.group(2).strip()),
    ),
]


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

async def dispatch(text: str, session_id: str) -> str | None:
    """Attempt to match *text* against known command patterns.

    Priority order:
      1. Computer-control commands (new)
      2. Legacy system commands
      3. Student productivity commands
      4. Return ``None`` → caller falls through to Gemini AI.

    Args:
        text: Raw user input string.
        session_id: Current session identifier (reserved for future use).

    Returns:
        A result string if a command matched, or ``None`` if no match was found.
    """
    import inspect

    # Computer-control patterns use a callable_factory instead of a direct
    # function reference so modules load lazily.
    for pattern, handler_factory, arg_extractor in _COMPUTER_CONTROL_PATTERNS:
        match = pattern.search(text)
        if match:
            try:
                handler = handler_factory()  # type: ignore[operator]
                args = arg_extractor(match)
                logger.info(
                    "Computer-control command matched: pattern=%s args=%s",
                    pattern.pattern,
                    args,
                )
                if inspect.iscoroutinefunction(handler):
                    result = await handler(*args)
                else:
                    result = handler(*args)
                return str(result)
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("Computer-control handler error: %s", exc)
                return f"Command failed: {exc}"

    # Natural-language reminder patterns (before legacy patterns)
    if _NL_REMINDER_TRIGGERS.search(text):
        return await _nl_reminder_handler(text)

    # Legacy patterns (direct function references)
    for pattern, handler, arg_extractor in _SYSTEM_PATTERNS + _STUDENT_PATTERNS:
        match = pattern.search(text)
        if match:
            args = arg_extractor(match)
            logger.info(
                "Command matched: pattern=%s args=%s", pattern.pattern, args
            )
            try:
                if inspect.iscoroutinefunction(handler):
                    result = await handler(*args)  # type: ignore[operator]
                else:
                    result = handler(*args)  # type: ignore[operator]
                return str(result)
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("Command handler error: %s", exc)
                return f"Command failed: {exc}"

    return None
