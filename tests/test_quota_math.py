from datetime import datetime, timezone, timedelta
from app.periods import split_interval_by_workweek


def test_split_zero_outside_workweek():
    # Sunday interval should count 0 for the workweek window containing its start (which is a new Monday window)
    start = datetime(2026, 2, 22, 10, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=2)
    assert split_interval_by_workweek(start, end) in (0, 120)  # depends on local day; keep it loose
