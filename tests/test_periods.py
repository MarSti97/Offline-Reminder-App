from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

import app.periods as periods


TZ = ZoneInfo("Europe/Lisbon")


def _dt_local(y, m, d, hh=0, mm=0, ss=0):
    return datetime(y, m, d, hh, mm, ss, tzinfo=TZ)


def _dt_utc(y, m, d, hh=0, mm=0, ss=0):
    return datetime(y, m, d, hh, mm, ss, tzinfo=timezone.utc)


def test_workweek_window_for_midweek(monkeypatch):
    monkeypatch.setattr(periods, "local_tz", lambda: TZ)

    dt = _dt_local(2026, 2, 18, 12, 0)  # Wed
    w = periods.workweek_window_for(dt)

    assert w.start_local == _dt_local(2026, 2, 16, 0, 0)  # Monday
    assert w.end_local == _dt_local(2026, 2, 21, 0, 0)    # Saturday 00:00


def test_period_key_workweek_keys_by_monday(monkeypatch):
    monkeypatch.setattr(periods, "local_tz", lambda: TZ)

    dt = _dt_local(2026, 2, 20, 9, 0)  # Fri
    assert periods.period_key_workweek(dt) == "workweek:2026-02-16"


def test_is_in_workweek_boundaries(monkeypatch):
    monkeypatch.setattr(periods, "local_tz", lambda: TZ)

    mon_start = _dt_local(2026, 2, 16, 0, 0)
    fri_late = _dt_local(2026, 2, 20, 23, 59)
    sat_start = _dt_local(2026, 2, 21, 0, 0)

    assert periods.is_in_workweek(mon_start) is True
    assert periods.is_in_workweek(fri_late) is True
    assert periods.is_in_workweek(sat_start) is False  # exclusive end


def test_next_reminder_datetime_local(monkeypatch):
    monkeypatch.setattr(periods, "local_tz", lambda: TZ)

    dt = _dt_local(2026, 2, 18, 8, 30)
    rem = periods.next_reminder_datetime_local(dt, time(9, 0))
    assert rem == _dt_local(2026, 2, 18, 9, 0)


def test_split_interval_by_workweek_counts_only_inside_window(monkeypatch):
    """
    Session crosses Fri->Sat boundary.
    Count only minutes until Sat 00:00 local.
    """
    monkeypatch.setattr(periods, "local_tz", lambda: TZ)

    # Fri 23:30 local -> Sat 00:30 local
    start_local = _dt_local(2026, 2, 20, 23, 30)
    end_local = _dt_local(2026, 2, 21, 0, 30)

    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)

    mins = periods.split_interval_by_workweek(start_utc, end_utc)
    assert mins == 30


def test_split_interval_by_workweek_ignores_outside_workweek(monkeypatch):
    """
    Entire interval on Saturday should count 0.
    (Because it intersects the workweek window that contains the *start* local time.)
    """
    monkeypatch.setattr(periods, "local_tz", lambda: TZ)

    start_local = _dt_local(2026, 2, 21, 10, 0)  # Saturday
    end_local = _dt_local(2026, 2, 21, 11, 0)

    mins = periods.split_interval_by_workweek(
        start_local.astimezone(timezone.utc),
        end_local.astimezone(timezone.utc),
    )
    assert mins == 0


def test_dst_week_does_not_crash_and_boundaries_hold(monkeypatch):
    """
    Europe/Lisbon DST starts last Sunday of March.
    Workweek boundaries should still be Mon 00:00 -> Sat 00:00 local.
    """
    monkeypatch.setattr(periods, "local_tz", lambda: TZ)

    # Pick a date during DST-change week: Wed 2026-03-25
    dt = _dt_local(2026, 3, 25, 12, 0)
    w = periods.workweek_window_for(dt)

    assert w.start_local.date().isoformat() == "2026-03-23"
    assert w.end_local.date().isoformat() == "2026-03-28"
    assert w.start_local.hour == 0 and w.start_local.minute == 0
    assert w.end_local.hour == 0 and w.end_local.minute == 0

    # A short interval on Friday evening should still count correctly.
    start_local = _dt_local(2026, 3, 27, 23, 0)
    end_local = _dt_local(2026, 3, 27, 23, 30)
    mins = periods.split_interval_by_workweek(
        start_local.astimezone(timezone.utc),
        end_local.astimezone(timezone.utc),
    )
    assert mins == 30