from datetime import datetime

from config import TEACHER_TIMEZONE


def format_time_remaining(deadline: datetime) -> str:
    """Return a human-friendly 'time until deadline' string.

    Handles granularity based on urgency:
    - More than 1 day: "2d 4h"
    - 1-24 hours: "6h 23m"
    - Under 1 hour: "45 minutes"
    - Under 5 minutes: "a few minutes"
    - Past deadline: "⚠️ Overdue by ..."

    `deadline` is expected to be timezone-aware (tzinfo set).
    """
    now = datetime.now(TEACHER_TIMEZONE)

    # Make sure the deadline is tz-aware. If it came from SQLite it may be naive;
    # assume it's in teacher timezone in that case.
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=TEACHER_TIMEZONE)

    delta = deadline - now
    total_seconds = int(delta.total_seconds())

    if total_seconds < 0:
        # Overdue
        overdue_seconds = -total_seconds
        return "⚠️ Overdue by " + _format_short(overdue_seconds)

    if total_seconds < 5 * 60:
        return "⏳ Due in a few minutes!"

    if total_seconds < 60 * 60:
        minutes = total_seconds // 60
        return f"⏳ Due in {minutes} minutes"

    if total_seconds < 24 * 60 * 60:
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        if minutes == 0:
            return f"⏳ Due in {hours}h"
        return f"⏳ Due in {hours}h {minutes}m"

    # More than 24 hours
    days = total_seconds // (24 * 3600)
    hours = (total_seconds % (24 * 3600)) // 3600
    if hours == 0:
        return f"⏳ Due in {days}d"
    return f"⏳ Due in {days}d {hours}h"


def _format_short(seconds: int) -> str:
    """Short form for overdue durations: '3h', '2d 4h', '45m'."""
    if seconds < 60 * 60:
        return f"{seconds // 60}m"
    if seconds < 24 * 60 * 60:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        if minutes == 0:
            return f"{hours}h"
        return f"{hours}h {minutes}m"
    days = seconds // (24 * 3600)
    hours = (seconds % (24 * 3600)) // 3600
    if hours == 0:
        return f"{days}d"
    return f"{days}d {hours}h"