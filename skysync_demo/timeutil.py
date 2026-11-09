"""
Time helpers.

Every timestamp in the system is stored as a *naive UTC* ISO-8601 string without
microseconds, e.g. ``"2026-11-09T08:30:00"``. The screens append ``Z`` before
showing it in the viewer's local time.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

MINUTE = timedelta(minutes=1)
HOUR = timedelta(hours=1)
DAY = timedelta(days=1)


def utcnow() -> datetime:
    """Current time as a naive UTC datetime, rounded to the second."""
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def iso(moment: datetime) -> str:
    """``datetime`` → ``"YYYY-MM-DDTHH:MM:SS"``."""
    return moment.replace(microsecond=0).isoformat()


def parse(value: str | None) -> datetime | None:
    """ISO string (with or without a trailing ``Z``) → naive UTC ``datetime``."""
    if not value:
        return None
    return datetime.fromisoformat(value.removesuffix("Z"))


def hours_between(start: str, end: str) -> float:
    """Hours from one ISO timestamp to another."""
    return (parse(end) - parse(start)).total_seconds() / 3600
