from __future__ import annotations
from typing import Optional, List
from PySide6.QtCore import Qt, QTime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QCheckBox, QSpinBox, QTimeEdit, QComboBox, QWidget
)

from ..models import TaskType
from ..repository import Repository


WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


class TaskEditor(QDialog):
    def __init__(self, repo: Repository, task_id: Optional[int] = None, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.task_id = task_id
        self.setWindowTitle("Edit Task" if task_id else "Add Task")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)

        self.title = QLineEdit()
        layout.addWidget(QLabel("Title"))
        layout.addWidget(self.title)

        self.enabled = QCheckBox("Enabled")
        self.enabled.setChecked(True)
        layout.addWidget(self.enabled)

        self.task_type = QComboBox()
        self.task_type.addItem("Weekly time quota", TaskType.WEEKLY_TIME_QUOTA.value)
        self.task_type.addItem("Complete once per workweek", TaskType.COMPLETE_ONCE.value)
        self.task_type.currentIndexChanged.connect(self._toggle_fields)
        layout.addWidget(QLabel("Task Type"))
        layout.addWidget(self.task_type)

        self.goal_minutes = QSpinBox()
        self.goal_minutes.setRange(1, 10_000)
        self.goal_minutes.setValue(60)
        layout.addWidget(QLabel("Weekly goal minutes (quota tasks)"))
        layout.addWidget(self.goal_minutes)

        layout.addWidget(QLabel("Active weekdays"))
        wd_row = QHBoxLayout()
        self.weekday_checks: List[QCheckBox] = []
        for i, lab in enumerate(WEEKDAY_LABELS):
            cb = QCheckBox(lab)
            cb.setChecked(i < 5)  # default Mon-Fri
            self.weekday_checks.append(cb)
            wd_row.addWidget(cb)
        layout.addLayout(wd_row)

        btns = QHBoxLayout()
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btns.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("Save")
        self.btn_save.clicked.connect(self.save)
        btns.addWidget(self.btn_save)
        layout.addLayout(btns)

        if task_id is not None:
            self._load(task_id)

        self._toggle_fields()

    def _toggle_fields(self) -> None:
        ttype = TaskType(self.task_type.currentData())
        is_quota = ttype == TaskType.WEEKLY_TIME_QUOTA
        self.goal_minutes.setEnabled(is_quota)

    def _load(self, task_id: int) -> None:
        t = self.repo.get_task(task_id)
        self.title.setText(t.title)
        self.enabled.setChecked(t.enabled)
        idx = 0 if t.task_type == TaskType.WEEKLY_TIME_QUOTA else 1
        self.task_type.setCurrentIndex(idx)
        if t.weekly_goal_minutes:
            self.goal_minutes.setValue(int(t.weekly_goal_minutes))

        for i, cb in enumerate(self.weekday_checks):
            cb.setChecked(i in t.schedule.active_weekdays)

    def save(self) -> None:
        title = self.title.text().strip() or "Untitled"
        enabled = self.enabled.isChecked()
        ttype = TaskType(self.task_type.currentData())
        hhmm = "9:00"
        weekdays = [i for i, cb in enumerate(self.weekday_checks) if cb.isChecked()]

        weekly_goal = int(self.goal_minutes.value()) if ttype == TaskType.WEEKLY_TIME_QUOTA else None

        if self.task_id is None:
            self.repo.create_task(
                title=title,
                task_type=ttype,
                enabled=enabled,
                reminder_time_hhmm=hhmm,
                active_weekdays=weekdays,
                weekly_goal_minutes=weekly_goal,
            )
        else:
            self.repo.update_task(
                task_id=self.task_id,
                title=title,
                enabled=enabled,
                reminder_time_hhmm=hhmm,
                active_weekdays=weekdays,
                weekly_goal_minutes=weekly_goal,
            )
        self.accept()
