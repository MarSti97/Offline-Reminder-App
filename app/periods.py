from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, time, date, timezone, tzinfo
from zoneinfo import ZoneInfo
from typing import Tuple, Optional

def local_tz() -> tzinfo:
    return datetime.now().astimezone().tzinfo  # type: ignore

def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def to_utc(dt_local: datetime) -> datetime:
    if dt_local.tzinfo is None:
        raise ValueError("dt_local must be timezone-aware")
    return dt_local.astimezone(timezone.utc)


def to_local(dt_utc: datetime) -> datetime:
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=timezone.utc)
    return dt_utc.astimezone(local_tz())


@dataclass(frozen=True)
class WorkWeekWindow:
    start_local: datetime  # Mon 00:00 local (inclusive)
    end_local: datetime    # Sat 00:00 local (exclusive)


def workweek_window_for(dt_local: datetime) -> WorkWeekWindow:
    """Work week is Monday 00:00 through Saturday 00:00 (exclusive)."""
    if dt_local.tzinfo is None:
        raise ValueError("dt_local must be timezone-aware")

    # normalize to local midnight
    d = dt_local.date()
    weekday = dt_local.weekday()  # Mon=0
    # find Monday of this week
    monday = d - timedelta(days=weekday)
    start = datetime.combine(monday, time(0, 0), tzinfo=dt_local.tzinfo)
    end = start + timedelta(days=5)  # Saturday 00:00
    return WorkWeekWindow(start_local=start, end_local=end)


def period_key_workweek(dt_local: datetime) -> str:
    w = workweek_window_for(dt_local)
    # key by Monday date
    monday = w.start_local.date().isoformat()
    return f"workweek:{monday}"


def is_in_workweek(dt_local: datetime) -> bool:
    w = workweek_window_for(dt_local)
    return w.start_local <= dt_local < w.end_local


def next_reminder_datetime_local(dt_local: datetime, reminder_time: time) -> datetime:
    """Today at reminder time (local)."""
    return datetime.combine(dt_local.date(), reminder_time, tzinfo=dt_local.tzinfo)


def split_interval_by_workweek(start_utc: datetime, end_utc: datetime) -> int:
    """
    Return number of whole minutes that fall within the workweek window
    that contains start_utc (local), and also handles crossing Fri->Sat boundary
    by counting only the intersection with that window.
    """
    if start_utc.tzinfo is None:
        start_utc = start_utc.replace(tzinfo=timezone.utc)
    if end_utc.tzinfo is None:
        end_utc = end_utc.replace(tzinfo=timezone.utc)

    start_local = to_local(start_utc)
    end_local = to_local(end_utc)

    w = workweek_window_for(start_local)

    # intersect [start_local, end_local) with [w.start_local, w.end_local)
    a = max(start_local, w.start_local)
    b = min(end_local, w.end_local)

    if b <= a:
        return 0

    seconds = (b - a).total_seconds()
    return int(seconds // 60)
