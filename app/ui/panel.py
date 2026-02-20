from __future__ import annotations
from datetime import datetime, timedelta, time as dtime, timezone
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget, QListWidgetItem,
    QSpinBox, QTimeEdit, QMessageBox, QMenu
)

from ..engine import compute_task_state
from ..repository import Repository
from ..models import TaskType
from ..periods import now_utc, to_local
from .task_editor import TaskEditor


class TrayPanel(QDialog):
    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.setWindowTitle("Reminders")
        self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setMinimumWidth(520)
        self.setAttribute(Qt.WA_DeleteOnClose, False)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self.refresh)

        # Start/stop timer based on visibility
        self._refresh_timer.setInterval(15_000)  # default while visible but idle

        self.layout = QVBoxLayout(self)
        self.header = QLabel("Tasks")
        self.layout.addWidget(self.header)

        self.list = QListWidget()
        self.layout.addWidget(self.list)

        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._show_task_menu_at)

        # --- Manage tasks row ---
        manage_row = QHBoxLayout()

        self.btn_add_task = QPushButton("Add task…")
        self.btn_add_task.clicked.connect(self.add_task)
        manage_row.addWidget(self.btn_add_task)

        self.btn_edit_task = QPushButton("Edit task…")
        self.btn_edit_task.clicked.connect(self.edit_task)
        manage_row.addWidget(self.btn_edit_task)

        self.btn_delete_task = QPushButton("Delete task")
        self.btn_delete_task.clicked.connect(self.delete_task)
        manage_row.addWidget(self.btn_delete_task)

        self.layout.addLayout(manage_row)

        self.footer = QLabel("Right-click a task for more options")
        self.footer.setStyleSheet("""
            QLabel {
                color: #888;
                font-size: 11px;
                padding-top: 6px;
            }
        """)
        self.footer.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.footer)

        self.refresh()

    def selected_task_id(self) -> Optional[int]:
        item = self.list.currentItem()
        if not item:
            return None
        return int(item.data(Qt.UserRole))
    
    def _any_session_running(self) -> bool:
        # Cheap approach: ask repo per task (fine for small task lists)
        for t in self.repo.list_tasks():
            if t.task_type == TaskType.WEEKLY_TIME_QUOTA and self.repo.is_session_running(t.id):
                return True
        return False
    
    def _update_refresh_timer_interval(self) -> None:
        # Faster refresh when at least one timer is running
        interval_ms = 2_000 if self._any_session_running() else 15_000
        if self._refresh_timer.interval() != interval_ms:
            self._refresh_timer.setInterval(interval_ms)

    def refresh(self) -> None:
        self._update_refresh_timer_interval()
        selected_id = self.selected_task_id()

        # ✅ Compute once
        settings = self.repo.get_settings()
        nowu = now_utc()
        nowl = to_local(nowu)
        today = nowl.date().isoformat()

        tasks = self.repo.list_tasks()

        self.list.blockSignals(True)
        try:
            self.list.clear()

            selected_row = None

            for idx, t in enumerate(tasks):
                snooze = self.repo.get_snooze_state(t.id)

                suffix = []
                if not t.enabled:
                    suffix.append("DISABLED")
                if snooze.skipped_date_local == today:
                    suffix.append("skipped today")
                if snooze.snoozed_until_utc:
                    suffix.append(f"snoozed until {snooze.snoozed_until_utc}")

                state = compute_task_state(self.repo, t, nowu, nowl, settings)
                status = state.status_text

                text = f"{t.title} — {status}"
                if suffix:
                    text += " [" + ", ".join(suffix) + "]"

                it = QListWidgetItem(text)
                it.setData(Qt.UserRole, t.id)
                self.list.addItem(it)

                if selected_id is not None and t.id == selected_id:
                    selected_row = idx

            if selected_row is not None:
                self.list.setCurrentRow(selected_row)

        finally:
            self.list.blockSignals(False)


    def _show_task_menu_at(self, pos) -> None:
        item = self.list.itemAt(pos)
        if item is None:
            return

        # Ensure the right-clicked item becomes selected
        self.list.setCurrentItem(item)

        tid = int(item.data(Qt.UserRole))
        self._open_task_menu(tid, self.list.mapToGlobal(pos))


    def _open_task_menu(self, tid: int, global_pos) -> None:
        t = self.repo.get_task(tid)

        menu = QMenu(self)

        menu.addAction("Skip this reminder for today").triggered.connect(lambda: self._skip_today(tid))
        menu.addSeparator()

        snooze = menu.addMenu("Snooze")
        snooze.addAction("30 minutes").triggered.connect(lambda: self._snooze_for(tid, 30))
        snooze.addAction("1 hour").triggered.connect(lambda: self._snooze_for(tid, 60))
        snooze.addAction("2 hours").triggered.connect(lambda: self._snooze_for(tid, 120))
        snooze.addAction("4 hours").triggered.connect(lambda: self._snooze_for(tid, 240))
        snooze.addSeparator()
        snooze.addAction("Until tomorrow at 09:00").triggered.connect(lambda: self._snooze_tomorrow_start(tid))

        menu.addAction("Clear snooze/skip").triggered.connect(lambda: self._clear_snooze_skip(tid))

        menu.addSeparator()
        if t.task_type == TaskType.WEEKLY_TIME_QUOTA:
            do_task = menu.addMenu("Do Task")
            label = "Stop Session" if self.repo.is_session_running(tid) else "Start Session"
            do_task.addAction(label).triggered.connect(lambda: self._toggle_session_for(tid))
            do_task.addSeparator()
            do_task.addAction("15 minutes done").triggered.connect(lambda: self._add_minutes_for(tid, 15))
            do_task.addAction("30 minutes done").triggered.connect(lambda: self._add_minutes_for(tid, 30))
            do_task.addAction("1 hour done").triggered.connect(lambda: self._add_minutes_for(tid, 60))
            do_task.addAction("2 hours done").triggered.connect(lambda: self._add_minutes_for(tid, 120))

        menu.addAction("Mark as complete").triggered.connect(lambda: self._mark_complete_for(tid))
        menu.addAction("Reset completion (this week)").triggered.connect(lambda: self._reset_completion(tid))

        if t.task_type == TaskType.WEEKLY_TIME_QUOTA:
            menu.addAction("Reset progress (this week)…").triggered.connect(lambda: self._reset_progress_confirm(tid))


        menu.exec(global_pos)


    def _snooze_for(self, task_id: int, minutes: int) -> None:
        until = now_utc() + timedelta(minutes=minutes)
        self.repo.set_snoozed_until_utc(task_id, until.isoformat())
        self.refresh()


    def _snooze_tomorrow_start(self, task_id: int) -> None:
        nowl = to_local(now_utc())
        tomorrow = nowl.date() + timedelta(days=1)

        settings = self.repo.get_settings()
        start_time = settings.reminder_start_time

        dt_local = datetime.combine(tomorrow, start_time, tzinfo=nowl.tzinfo)
        dt_utc = dt_local.astimezone(timezone.utc)

        self.repo.set_snoozed_until_utc(task_id, dt_utc.isoformat())
        self.refresh()


    def _skip_today(self, task_id: int) -> None:
        today = to_local(now_utc()).date().isoformat()
        self.repo.set_skipped_today_local(task_id, today)
        self.refresh()


    def _clear_snooze_skip(self, task_id: int) -> None:
        self.repo.clear_snooze_and_skip(task_id)
        self.refresh()


    def _reset_completion(self, task_id: int) -> None:
        # Removes manual completion override for the current workweek
        self.repo.clear_completion_for_current_period(task_id)
        self.refresh()


    def _reset_progress_confirm(self, task_id: int) -> None:
        confirm = QMessageBox.question(
            self,
            "Reset progress",
            "Reset this week's logged minutes for this task?\n\n"
            "This will delete this week's sessions and manual minute logs.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.repo.delete_sessions_for_current_workweek(task_id)
            # Also clear completion override so it becomes due again
            self.repo.clear_completion_for_current_period(task_id)
            self.refresh()

    def _toggle_session_for(self, task_id: int) -> None:
        t = self.repo.get_task(task_id)
        if t.task_type != TaskType.WEEKLY_TIME_QUOTA:
            return

        if self.repo.is_session_running(task_id):
            self.repo.stop_session(task_id)
        else:
            self.repo.start_session(task_id)

        self.refresh()


    def _add_minutes_for(self, task_id: int, minutes: int) -> None:
        t = self.repo.get_task(task_id)
        if t.task_type != TaskType.WEEKLY_TIME_QUOTA:
            return

        self.repo.add_manual_minutes(task_id, int(minutes))
        self.refresh()


    def _mark_complete_for(self, task_id: int) -> None:
        # Works for BOTH quota and complete-once
        t = self.repo.get_task(task_id)
        if t.task_type not in (TaskType.WEEKLY_TIME_QUOTA, TaskType.COMPLETE_ONCE):
            return

        self.repo.mark_complete_for_current_period(task_id)
        self.refresh()



    # -------- actions ----------
    def toggle_session(self) -> None:
        tid = self.selected_task_id()
        if tid is None:
            return
        self._toggle_session_for(tid)


    def add_minutes(self) -> None:
        tid = self.selected_task_id()
        if tid is None:
            return
        self._add_minutes_for(tid, int(self.add_minutes_box.value()))


    def mark_complete(self) -> None:
        tid = self.selected_task_id()
        if tid is None:
            return
        self._mark_complete_for(tid)


    def reset_current_period(self) -> None:
        tid = self.selected_task_id()
        if tid is None:
            return
        self.repo.clear_completion_for_current_period(tid)
        self.refresh()

    def skip_today(self) -> None:
        tid = self.selected_task_id()
        if tid is None:
            return
        today = to_local(now_utc()).date().isoformat()
        self.repo.set_skipped_today_local(tid, today)
        self.refresh()

    def clear_snooze_skip(self) -> None:
        tid = self.selected_task_id()
        if tid is None:
            return
        self.repo.clear_snooze_and_skip(tid)
        self.refresh()

    def open_snooze_menu(self) -> None:
        tid = self.selected_task_id()
        if tid is None:
            return

        menu = QMenu(self)
        menu.addAction("30 min").triggered.connect(lambda: self.snooze_for(tid, 30))
        menu.addAction("1 hour").triggered.connect(lambda: self.snooze_for(tid, 60))
        menu.addAction("2 hours").triggered.connect(lambda: self.snooze_for(tid, 120))
        menu.addAction("4 hours").triggered.connect(lambda: self.snooze_for(tid, 240))
        menu.addSeparator()
        menu.addAction("Tomorrow at reminder time").triggered.connect(lambda: self.snooze_tomorrow_at_reminder(tid))
        menu.exec(self.btn_snooze_menu.mapToGlobal(self.btn_snooze_menu.rect().bottomLeft()))

    def snooze_for(self, task_id: int, minutes: int) -> None:
        until = now_utc() + timedelta(minutes=minutes)
        self.repo.set_snoozed_until_utc(task_id, until.isoformat())
        self.refresh()

    def snooze_tomorrow_at_reminder(self, task_id: int) -> None:
        nowl = to_local(now_utc())
        tomorrow = nowl.date() + timedelta(days=1)

        settings = self.repo.get_settings()
        start_time = settings.reminders_start_time  # a datetime.time

        dt_local = datetime.combine(tomorrow, start_time, tzinfo=nowl.tzinfo)
        dt_utc = dt_local.astimezone(timezone.utc)

        self.repo.set_snoozed_until_utc(task_id, dt_utc.isoformat())
        self.refresh()

    def add_task(self) -> None:
        dlg = TaskEditor(self.repo, task_id=None, parent=self)
        if dlg.exec():
            self.refresh()

    def edit_task(self) -> None:
        tid = self.selected_task_id()
        if tid is None:
            QMessageBox.information(self, "No selection", "Select a task first.")
            return
        dlg = TaskEditor(self.repo, task_id=tid, parent=self)
        if dlg.exec():
            self.refresh()

    def delete_task(self) -> None:
        tid = self.selected_task_id()
        if tid is None:
            QMessageBox.information(self, "No selection", "Select a task first.")
            return

        confirm = QMessageBox.question(
            self,
            "Delete task",
            "Delete the selected task? This will also remove its sessions/completions.",
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.repo.delete_task(tid)
            self.refresh()

    def closeEvent(self, event):
        event.ignore()
        self.hide()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._refresh_timer.start()
        self.refresh()  # immediate refresh on open


    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._refresh_timer.stop()

