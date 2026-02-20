from __future__ import annotations
from PySide6.QtWidgets import QSystemTrayIcon
from PySide6.QtGui import QIcon


class Notifier:
    def __init__(self, tray: QSystemTrayIcon):
        self.tray = tray

    def remind(self, title: str, message: str) -> None:
        # Cross-platform "native-ish" balloon/toast
        self.tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 10_000)
