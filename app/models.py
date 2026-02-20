from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List
from datetime import time


class TaskType(str, Enum):
    WEEKLY_TIME_QUOTA = "weekly_time_quota"
    COMPLETE_ONCE = "complete_once"


@dataclass(frozen=True)
class WeekSchedule:
    # 0=Mon ... 6=Sun
    active_weekdays: List[int]


@dataclass(frozen=True)
class Task:
    id: int
    title: str
    task_type: TaskType
    enabled: bool
    schedule: WeekSchedule

    # For weekly time quota
    weekly_goal_minutes: Optional[int] = None

    # For complete-once tasks
    period: str = "workweek"  # MVP: "workweek" only


@dataclass(frozen=True)
class SnoozeState:
    snoozed_until_utc: Optional[str]  # ISO utc string
    skipped_date_local: Optional[str]  # YYYY-MM-DD in local time


@dataclass(frozen=True)
class AppSettings:
    start_at_login: bool
    repeat_interval_minutes: int  # how often to repeat reminders when due
    reminders_start_time: time
