"""Natural-language time parser for reminder scheduling.

Supports:
  - Relative: "in 10 minutes", "in 2 hours", "in 30 seconds", "in 1 day"
  - Absolute: "at 7 PM", "at 9:30 AM", "at 14:00"
  - Named:    "at noon", "at midnight"
  - Tomorrow: "tomorrow at 9 AM", "tomorrow morning"

Returns a ``datetime`` in local time, or ``None`` if unparseable.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_RELATIVE_RE = re.compile(
    r"in\s+(\d+(?:\.\d+)?)\s+"
    r"(second|minute|hour|day|week)s?",
    re.IGNORECASE,
)

_ABSOLUTE_RE = re.compile(
    r"at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?",
    re.IGNORECASE,
)

_NAMED_TIMES: dict[str, tuple[int, int]] = {
    "noon":     (12, 0),
    "midday":   (12, 0),
    "midnight": (0,  0),
    "morning":  (8,  0),
    "evening":  (18, 0),
    "night":    (21, 0),
}

_DELTA_MAP: dict[str, str] = {
    "second": "seconds",
    "minute": "minutes",
    "hour":   "hours",
    "day":    "days",
    "week":   "weeks",
}


def _add_day_if_past(dt: datetime, text: str, now: datetime) -> datetime:
    """If *dt* is in the past and 'tomorrow' is not in *text*, advance by 1 day."""
    if "tomorrow" in text.lower():
        return dt + timedelta(days=1)
    if dt <= now:
        return dt + timedelta(days=1)
    return dt


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_reminder_time(text: str) -> datetime | None:
    """Return a ``datetime`` parsed from *text*, or ``None``."""
    now = datetime.now().replace(second=0, microsecond=0)
    lower = text.lower()

    # 1. Relative: "in N unit(s)"
    m = _RELATIVE_RE.search(lower)
    if m:
        amount = float(m.group(1))
        unit   = m.group(2).lower()
        kw     = {_DELTA_MAP[unit]: amount}
        return now + timedelta(**kw)

    # 2. Named times: noon, midnight, …
    for name, (h, mi) in _NAMED_TIMES.items():
        if name in lower:
            target = now.replace(hour=h, minute=mi)
            return _add_day_if_past(target, lower, now)

    # 3. Absolute: "at H[:MM] [am|pm]"
    m = _ABSOLUTE_RE.search(lower)
    if m:
        hour   = int(m.group(1))
        minute = int(m.group(2) or 0)
        ampm   = (m.group(3) or "").lower()

        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0

        target = now.replace(hour=hour, minute=minute)
        return _add_day_if_past(target, lower, now)

    return None


def extract_reminder_info(text: str) -> tuple[str, datetime | None]:
    """Parse *text* and return ``(title, remind_at)``.

    Args:
        text: Raw user utterance such as
            ``"remind me in 10 minutes to take medicine"`` or
            ``"set alarm for 7 PM"``.

    Returns:
        Tuple of ``(title_string, datetime_or_None)``.
    """
    dt    = parse_reminder_time(text)
    lower = text.lower()

    # Try to extract the subject of the reminder
    title: str | None = None

    # "remind me … to <title>"
    m = re.search(r"\bto\s+(.+?)(?:\s+in\s+\d|\s+at\s+\d|$)", lower)
    if m:
        title = m.group(1).strip()

    # "remind me about <title>"
    if not title:
        m = re.search(r"\babout\s+(.+?)(?:\s+in\s+|\s+at\s+|$)", lower)
        if m:
            title = m.group(1).strip()

    # "set alarm for <time> <title>"
    if not title:
        m = re.search(r"alarm\s+for\s+\S+\s+(.+)", lower)
        if m:
            title = m.group(1).strip()

    if not title or len(title) < 2:
        title = "Reminder"

    # Capitalise first letter
    title = title[0].upper() + title[1:]

    return title, dt
