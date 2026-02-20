from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from .models import Task, TaskType, AppSettings
from .periods import is_in_workweek, next_reminder_datetime_local


@dataclass(frozen=True)
class TaskState:
    task_id: int
    title: str
    task_type: TaskType

    enabled: bool
    active_today: bool
    in_workweek: bool

    skipped_today: bool
    snoozed: bool
    snoozed_until_utc: Optional[str]

    running: bool

    completed_override: bool  # completion record exists for current period
    done_by_minutes: bool     # only for quota tasks
    done: bool               # done for the period, overall

    goal_minutes: Optional[int]
    done_minutes: Optional[int]

    # reminder gating
    can_remind_now: bool
    reminder_message: str

    # UI display
    status_text: str


def compute_task_state(repo, task: Task, nowu: datetime, nowl: datetime, settings: AppSettings) -> TaskState:
    """
    Single source of truth for:
    - DONE/DUE/RUNNING status
    - whether reminder is allowed right now (ignoring repeat throttling)
    """
    # Basic flags
    enabled = bool(task.enabled)
    in_workweek_flag = is_in_workweek(nowl)
    active_today = (nowl.weekday() in task.schedule.active_weekdays)

    # Snooze/skip
    snooze = repo.get_snooze_state(task.id)
    today = nowl.date().isoformat()
    skipped_today = (snooze.skipped_date_local == today)

    snoozed = False
    snoozed_until = snooze.snoozed_until_utc
    if snoozed_until:
        until = datetime.fromisoformat(snoozed_until)
        if until.tzinfo is None:
            until = until.replace(tzinfo=timezone.utc)
        if nowu < until:
            snoozed = True
        else:
            # Expired: clear it so state is consistent everywhere
            repo.set_snoozed_until_utc(task.id, None)
            snoozed_until = None

    # “After start time” gate
    rem_dt = next_reminder_datetime_local(nowl, settings.reminders_start_time)
    after_start_time = (nowl >= rem_dt)

    # Completion signals
    completed_override = repo.is_completed_for_current_period(task.id)

    running = False
    goal_minutes: Optional[int] = None
    done_minutes: Optional[int] = None
    done_by_minutes = False

    if task.task_type == TaskType.WEEKLY_TIME_QUOTA:
        running = repo.is_session_running(task.id)
        goal_minutes = int(task.weekly_goal_minutes or 0)
        done_minutes = int(repo.weekly_minutes_for_current_workweek(task.id))
        done_by_minutes = (goal_minutes > 0 and done_minutes >= goal_minutes)

        done = completed_override or done_by_minutes

        if done:
            status_text = "DONE (this workweek)"
            msg = "Done for this work week."
        else:
            suffix = " (running)" if running else ""
            status_text = f"{done_minutes}/{goal_minutes} min{suffix}"
            msg = f"Progress: {done_minutes}/{goal_minutes} min this work week. Open tray panel to log/snooze."
    else:
        done = completed_override
        status_text = "DONE" if done else "DUE"
        msg = "Due. Open tray panel to snooze/skip/complete."

    # Can remind now? (not including repeat throttling)
    # Note: running suppresses reminders only for quota tasks.
    running_blocks = (task.task_type == TaskType.WEEKLY_TIME_QUOTA and running)

    can_remind_now = (
        enabled
        and in_workweek_flag
        and active_today
        and after_start_time
        and not skipped_today
        and not snoozed
        and not done
        and not running_blocks
    )

    return TaskState(
        task_id=task.id,
        title=task.title,
        task_type=task.task_type,

        enabled=enabled,
        active_today=active_today,
        in_workweek=in_workweek_flag,

        skipped_today=skipped_today,
        snoozed=snoozed,
        snoozed_until_utc=snoozed_until,

        running=running,

        completed_override=completed_override,
        done_by_minutes=done_by_minutes,
        done=done,

        goal_minutes=goal_minutes,
        done_minutes=done_minutes,

        can_remind_now=can_remind_now,
        reminder_message=msg,

        status_text=status_text,
    )