from __future__ import annotations
import sqlite3
from pathlib import Path

DB_NAME = "reminder.sqlite3"


def data_dir(app_name: str = "OfflineReminder") -> Path:
    # Cross-platform local app data dir
    # macOS: ~/Library/Application Support/OfflineReminder
    # Windows: %APPDATA%\OfflineReminder
    home = Path.home()
    if _is_macos():
        base = home / "Library" / "Application Support"
    elif _is_windows():
        base = Path(_get_env("APPDATA", str(home)))
    else:
        base = home / ".local" / "share"
    d = base / app_name
    d.mkdir(parents=True, exist_ok=True)
    return d


def db_path() -> Path:
    return data_dir() / DB_NAME


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            task_type TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            reminder_time TEXT NOT NULL, -- HH:MM
            active_weekdays TEXT NOT NULL, -- CSV "0,1,2"
            weekly_goal_minutes INTEGER, -- nullable
            period TEXT NOT NULL DEFAULT 'workweek'
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            start_utc TEXT NOT NULL,
            end_utc TEXT, -- null if running
            manual_minutes INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS completions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            period_key TEXT NOT NULL, -- e.g. "workweek:2026-02-16"
            completed_utc TEXT NOT NULL,
            UNIQUE(task_id, period_key)
        );

        CREATE TABLE IF NOT EXISTS snoozes (
            task_id INTEGER PRIMARY KEY REFERENCES tasks(id) ON DELETE CASCADE,
            snoozed_until_utc TEXT,
            skipped_date_local TEXT
        );
        """
    )

    # (optional) keep old key or delete it; keeping is safer
    if conn.execute("SELECT value FROM settings WHERE key='start_at_login'").fetchone() is None:
        conn.execute("INSERT INTO settings(key,value) VALUES('start_at_login','0')")

    # Defaults if missing
    if conn.execute("SELECT value FROM settings WHERE key='repeat_interval_minutes'").fetchone() is None:
        conn.execute("INSERT INTO settings(key,value) VALUES('repeat_interval_minutes','5')")

    # Start time of daily reminders
    if conn.execute("SELECT value FROM settings WHERE key='reminder_start_hhmm'").fetchone() is None:
        conn.execute("INSERT INTO settings(key,value) VALUES('reminder_start_hhmm','09:00')")
        
    conn.commit()


def _is_windows() -> bool:
    import sys
    return sys.platform.startswith("win")


def _is_macos() -> bool:
    import sys
    return sys.platform == "darwin"


def _get_env(k: str, default: str) -> str:
    import os
    return os.environ.get(k, default)
