from __future__ import annotations
from PySide6.QtCore import QTime
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QCheckBox, QHBoxLayout, QPushButton, QSpinBox, QTimeEdit
from ..repository import Repository
from ..autostart import enable_start_at_login, is_start_at_login_enabled


class SettingsDialog(QDialog):
    def __init__(self, repo: Repository, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.setWindowTitle("Settings")
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)

        self.start_login = QCheckBox("Start at login")
        self.start_login.setChecked(is_start_at_login_enabled())
        layout.addWidget(self.start_login)

        layout.addWidget(QLabel("Reminder repeat interval (minutes)"))
        self.repeat_minutes = QSpinBox()
        self.repeat_minutes.setRange(5, 24 * 60)
        self.repeat_minutes.setValue(self.repo.get_settings().repeat_interval_minutes)
        layout.addWidget(self.repeat_minutes)

        layout.addWidget(QLabel("Reminder start time"))

        self.start_time = QTimeEdit()
        self.start_time.setDisplayFormat("HH:mm")
        st = self.repo.get_settings().reminders_start_time
        self.start_time.setTime(QTime(st.hour, st.minute))
        layout.addWidget(self.start_time)

        btns = QHBoxLayout()
        save = QPushButton("Save")
        save.clicked.connect(self.save)
        btns.addWidget(save)

        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)

        layout.addLayout(btns)

    def save(self) -> None:
        enable = self.start_login.isChecked()
        enable_start_at_login(enable)
        self.repo.set_start_at_login(enable)
        self.repo.set_repeat_interval_minutes(int(self.repeat_minutes.value()))

        hh = self.start_time.time().hour()
        mm = self.start_time.time().minute()
        self.repo.set_reminder_start_hhmm(f"{hh:02d}:{mm:02d}")
        
        self.accept()
