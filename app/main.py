from __future__ import annotations
import sys
import signal

from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction, QCursor
from PySide6.QtCore import QTimer

from .db import connect, migrate
from .repository import Repository
from .resources import tray_icon
from .models import TaskType
from .scheduler import Scheduler, ReminderEvent
from .notifications import Notifier
from .ui.panel import TrayPanel
from .ui.task_editor import TaskEditor
from .ui.settings import SettingsDialog


def ensure_default_task(repo: Repository) -> None:
    tasks = repo.list_tasks()
    if tasks:
        return

    # Default: "Weekly Learning (60 min)" Mon-Fri at 11:00
    repo.create_task(
        title="Weekly Learning (60 min)",
        task_type=TaskType.WEEKLY_TIME_QUOTA,
        enabled=True,
        reminder_time_hhmm="11:00",
        active_weekdays=[0, 1, 2, 3, 4],
        weekly_goal_minutes=60,
    )

    # Example second task (disabled by default)
    repo.create_task(
        title="Single weekly task example reminder",
        task_type=TaskType.COMPLETE_ONCE,
        enabled=False,
        reminder_time_hhmm="16:00",
        active_weekdays=[4],  # Friday
        weekly_goal_minutes=None,
    )


def main() -> int:
    app = QApplication(sys.argv)
    app.setWindowIcon(tray_icon())
    app.setQuitOnLastWindowClosed(False)

    # --- Dev convenience: allow Ctrl-C to quit without ugly tracebacks ---
    # Qt's event loop eats SIGINT unless we pump it. This makes Ctrl-C behave.
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    _sig_timer = QTimer()
    _sig_timer.start(250)
    _sig_timer.timeout.connect(lambda: None)

    conn = connect()
    migrate(conn)
    repo = Repository(conn)
    ensure_default_task(repo)

    tray = QSystemTrayIcon()
    tray.setIcon(tray_icon())
    tray.setToolTip("Offline Reminder")

    panel = TrayPanel(repo)

    tray.messageClicked.connect(lambda: _show_panel(panel))

    menu = QMenu()

    act_open = QAction("Open")
    act_open.triggered.connect(lambda: _show_panel(panel))
    menu.addAction(act_open)

    menu.addSeparator()

    act_settings = QAction("Settings…")
    act_settings.triggered.connect(lambda: _open_settings(repo, panel))
    menu.addAction(act_settings)

    menu.addSeparator()

    def quit_cleanly():
        # Ensure tray icon disappears immediately; avoids some Qt shutdown warnings.
        tray.hide()
        panel.close()
        app.quit()

    act_quit = QAction("Quit")
    act_quit.triggered.connect(quit_cleanly)
    menu.addAction(act_quit)

    tray.setContextMenu(menu)

    if sys.platform.startswith("win"):
        def _show_menu_on_left_click(reason: QSystemTrayIcon.ActivationReason):
            if reason == QSystemTrayIcon.ActivationReason.Trigger:
                cm = tray.contextMenu()
                if cm is not None:
                    cm.popup(QCursor.pos())

        tray.activated.connect(_show_menu_on_left_click)

    notifier = Notifier(tray)

    scheduler = Scheduler(repo)
    scheduler.reminder_due.connect(lambda ev: _on_reminder(ev, notifier, panel))
    scheduler.start()

    tray.show()
    return app.exec()



def _tray_click(reason: QSystemTrayIcon.ActivationReason, panel) -> None:
    # Left-click on tray icon (macOS/Windows)
    if reason in (
        QSystemTrayIcon.ActivationReason.Trigger,
        QSystemTrayIcon.ActivationReason.DoubleClick,
        QSystemTrayIcon.ActivationReason.MiddleClick,
    ):
        _show_panel(panel)


def _show_panel(panel: TrayPanel) -> None:
    panel.refresh()
    panel.show()
    panel.raise_()
    panel.activateWindow()


def _on_reminder(ev: ReminderEvent, notifier: Notifier, panel: TrayPanel) -> None:
    notifier.remind(ev.title, ev.message)
    # also refresh panel state (in case user opens it)
    panel.refresh()


def _add_task(repo: Repository, panel: TrayPanel) -> None:
    dlg = TaskEditor(repo, task_id=None, parent=panel)
    if dlg.exec():
        panel.refresh()


def _edit_selected(repo: Repository, panel: TrayPanel) -> None:
    _show_panel(panel)
    tid = panel.selected_task_id()
    if tid is None:
        return
    dlg = TaskEditor(repo, task_id=tid, parent=panel)
    if dlg.exec():
        panel.refresh()


def _delete_selected(repo: Repository, panel: TrayPanel) -> None:
    _show_panel(panel)
    tid = panel.selected_task_id()
    if tid is None:
        return
    repo.delete_task(tid)
    panel.refresh()


def _open_settings(repo: Repository, panel: TrayPanel) -> None:
    dlg = SettingsDialog(repo, parent=panel)
    if dlg.exec():
        panel.refresh()
