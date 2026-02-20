from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional
from PySide6.QtCore import QObject, QTimer, Signal

from .engine import compute_task_state
from .models import TaskType
from .repository import Repository
from .periods import now_utc, to_local, next_reminder_datetime_local, is_in_workweek


@dataclass
class ReminderEvent:
    task_id: int
    title: str
    message: str


class Scheduler(QObject):
    reminder_due = Signal(object)  # ReminderEvent

    def __init__(self, repo: Repository, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.repo = repo
        self.timer = QTimer(self)
        self.timer.setInterval(30_000)  # 30s tick
        self.timer.timeout.connect(self.tick)
        self.repeat_interval_minutes = 5

        # prevent spam if ignored: per task, don't re-fire within 5 minutes unless snooze changes
        self.last_fired_utc: Dict[int, datetime] = {}

    def start(self) -> None:
        self.timer.start()
        # also check shortly after launch
        QTimer.singleShot(15_000, self.tick)

    def tick(self) -> None:
        nowu = now_utc()
        nowl = to_local(nowu)

        settings = self.repo.get_settings()
        repeat_minutes = max(1, int(settings.repeat_interval_minutes))

        tasks = self.repo.list_tasks()
        for t in tasks:
            state = compute_task_state(self.repo, t, nowu, nowl, settings)

            if not state.can_remind_now:
                continue

            if self._should_throttle(t.id, nowu, repeat_minutes):
                continue

            self._fire(t.id, t.title, state.reminder_message, nowu)

    def _should_throttle(self, task_id: int, nowu: datetime, repeat_minutes: int) -> bool:
        last = self.last_fired_utc.get(task_id)
        if not last:
            return False
        return (nowu - last) < timedelta(minutes=repeat_minutes)

    def _fire(self, task_id: int, title: str, message: str, nowu: datetime) -> None:
        self.last_fired_utc[task_id] = nowu
        self.reminder_due.emit(ReminderEvent(task_id=task_id, title=title, message=message))
