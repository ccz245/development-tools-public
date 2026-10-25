"""Small display formatters shared by the cards."""

from __future__ import annotations

from datetime import datetime, timedelta


def duration(delta: timedelta) -> str:
    """'1d 9h', '4h 16m', '12m', '<1m'."""
    minutes = int(delta.total_seconds() // 60)
    if minutes < 1:
        return "<1m"
    days, rest = divmod(minutes, 1440)
    hours, mins = divmod(rest, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {mins}m"
    return f"{mins}m"


def idle(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60:02d}s"
    return f"{seconds // 3600}h {seconds % 3600 // 60:02d}m"


def money(value: float) -> str:
    return f"${value:,.0f}" if value >= 10 else f"${value:,.2f}"


def temp(value: float | None) -> str:
    return "—" if value is None else f"{round(value)}°"


def percent(value: float | None) -> str:
    return "—" if value is None else f"{round(value)}%"


def stamp(when: datetime, now: datetime | None = None) -> str:
    """'17:27' for today, 'Oct 23 16:29' for earlier days."""
    now = now or datetime.now()
    return f"{when:%H:%M}" if when.date() == now.date() else f"{when:%b} {when.day} {when:%H:%M}"
