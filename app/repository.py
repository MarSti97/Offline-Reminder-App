from __future__ import annotations
import sqlite3
from datetime import datetime, timezone, time
from typing import List, Optional, Tuple
from .models import Task, TaskType, WeekSchedule, SnoozeState, AppSettings
from .periods import now_utc, to_local, period_key_workweek, split_interval_by_workweek

def _weekdays_from_csv(s: str) -> List[int]:
    if not s.strip():
        return []
    return [int(x) for x in s.split(",")]


def _weekdays_to_csv(days: List[int]) -> str:
    return ",".join(str(d) for d in sorted(set(days)))


class Repository:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # ---------- Settings ----------
    def get_settings(self) -> AppSettings:
        start = int(self._get_setting("start_at_login", "0")) == 1
        repeat = int(self._get_setting("repeat_interval_minutes", "5"))
        hhmm = self._get_setting("reminder_start_hhmm", "09:00")
        start_time = self._parse_hhmm(hhmm, time(9, 0))
        return AppSettings(start_at_login=start, repeat_interval_minutes=repeat, reminders_start_time=start_time)

    def set_start_at_login(self, enabled: bool) -> None:
        self._set_setting("start_at_login", "1" if enabled else "0")

    def set_repeat_interval_minutes(self, minutes: int) -> None:
        self._set_setting("repeat_interval_minutes", str(minutes))

    def set_reminder_start_hhmm(self, hhmm: str) -> None:
        self._set_setting("reminder_start_hhmm", hhmm)

    def _get_setting(self, key: str, default: str) -> str:
        row = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def _set_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self.conn.commit()

    # ---------- Tasks ----------
    def list_tasks(self) -> List[Task]:
        rows = self.conn.execute("SELECT * FROM tasks ORDER BY id ASC").fetchall()
        out: List[Task] = []
        for r in rows:
            sched = WeekSchedule(
                active_weekdays=_weekdays_from_csv(r["active_weekdays"]),
            )
            out.append(
                Task(
                    id=r["id"],
                    title=r["title"],
                    task_type=TaskType(r["task_type"]),
                    enabled=bool(r["enabled"]),
                    schedule=sched,
                    weekly_goal_minutes=r["weekly_goal_minutes"],
                    period=r["period"],
                )
            )
        return out

    def get_task(self, task_id: int) -> Task:
        r = self.conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not r:
            raise KeyError(task_id)
        sched = WeekSchedule(
            active_weekdays=_weekdays_from_csv(r["active_weekdays"]),
        )
        return Task(
            id=r["id"],
            title=r["title"],
            task_type=TaskType(r["task_type"]),
            enabled=bool(r["enabled"]),
            schedule=sched,
            weekly_goal_minutes=r["weekly_goal_minutes"],
            period=r["period"],
        )

    def create_task(
        self,
        title: str,
        task_type: TaskType,
        enabled: bool,
        reminder_time_hhmm: str,
        active_weekdays: List[int],
        weekly_goal_minutes: Optional[int] = None,
        period: str = "workweek",
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO tasks(title, task_type, enabled, reminder_time, active_weekdays, weekly_goal_minutes, period)
            VALUES(?,?,?,?,?,?,?)
            """,
            (
                title,
                task_type.value,
                1 if enabled else 0,
                reminder_time_hhmm,
                _weekdays_to_csv(active_weekdays),
                weekly_goal_minutes,
                period,
            ),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def update_task(
        self,
        task_id: int,
        title: str,
        enabled: bool,
        reminder_time_hhmm: str,
        active_weekdays: List[int],
        weekly_goal_minutes: Optional[int] = None,
    ) -> None:
        self.conn.execute(
            """
            UPDATE tasks
            SET title=?, enabled=?, reminder_time=?, active_weekdays=?, weekly_goal_minutes=?
            WHERE id=?
            """,
            (
                title,
                1 if enabled else 0,
                reminder_time_hhmm,
                _weekdays_to_csv(active_weekdays),
                weekly_goal_minutes,
                task_id,
            ),
        )
        self.conn.commit()

    def delete_task(self, task_id: int) -> None:
        self.conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        self.conn.commit()

    def _parse_hhmm(self, s: str, default: time) -> time:
        try:
            hh, mm = s.split(":")
            return time(int(hh), int(mm))
        except Exception:
            return default  

    # ---------- Snooze / Skip ----------
    def get_snooze_state(self, task_id: int) -> SnoozeState:
        r = self.conn.execute("SELECT * FROM snoozes WHERE task_id=?", (task_id,)).fetchone()
        if not r:
            return SnoozeState(snoozed_until_utc=None, skipped_date_local=None)
        return SnoozeState(
            snoozed_until_utc=r["snoozed_until_utc"],
            skipped_date_local=r["skipped_date_local"],
        )

    def set_snoozed_until_utc(self, task_id: int, iso_utc: Optional[str]) -> None:
        self.conn.execute(
            """
            INSERT INTO snoozes(task_id, snoozed_until_utc, skipped_date_local)
            VALUES(?,?,NULL)
            ON CONFLICT(task_id) DO UPDATE SET snoozed_until_utc=excluded.snoozed_until_utc
            """,
            (task_id, iso_utc),
        )
        self.conn.commit()

    def set_skipped_today_local(self, task_id: int, yyyy_mm_dd: Optional[str]) -> None:
        self.conn.execute(
            """
            INSERT INTO snoozes(task_id, snoozed_until_utc, skipped_date_local)
            VALUES(?,NULL,?)
            ON CONFLICT(task_id) DO UPDATE SET skipped_date_local=excluded.skipped_date_local
            """,
            (task_id, yyyy_mm_dd),
        )
        self.conn.commit()

    def clear_snooze_and_skip(self, task_id: int) -> None:
        self.conn.execute(
            """
            INSERT INTO snoozes(task_id, snoozed_until_utc, skipped_date_local)
            VALUES(?,NULL,NULL)
            ON CONFLICT(task_id) DO UPDATE SET snoozed_until_utc=NULL, skipped_date_local=NULL
            """,
            (task_id,),
        )
        self.conn.commit()

    # ---------- Sessions / Progress ----------
    def start_session(self, task_id: int) -> None:
        # Only one running session per task in MVP.
        running = self.conn.execute(
            "SELECT id FROM sessions WHERE task_id=? AND end_utc IS NULL AND manual_minutes=0",
            (task_id,),
        ).fetchone()
        if running:
            return
        self.conn.execute(
            "INSERT INTO sessions(task_id, start_utc, end_utc, manual_minutes) VALUES(?,?,NULL,0)",
            (task_id, now_utc().isoformat()),
        )
        self.conn.commit()

    def stop_session(self, task_id: int) -> None:
        r = self.conn.execute(
            "SELECT id FROM sessions WHERE task_id=? AND end_utc IS NULL AND manual_minutes=0",
            (task_id,),
        ).fetchone()
        if not r:
            return
        self.conn.execute(
            "UPDATE sessions SET end_utc=? WHERE id=?",
            (now_utc().isoformat(), r["id"]),
        )
        self.conn.commit()

    def is_session_running(self, task_id: int) -> bool:
        r = self.conn.execute(
            "SELECT 1 FROM sessions WHERE task_id=? AND end_utc IS NULL AND manual_minutes=0",
            (task_id,),
        ).fetchone()
        return bool(r)

    def add_manual_minutes(self, task_id: int, minutes: int) -> None:
        self.conn.execute(
            "INSERT INTO sessions(task_id, start_utc, end_utc, manual_minutes) VALUES(?,?,?,?)",
            (task_id, now_utc().isoformat(), now_utc().isoformat(), int(minutes)),
        )
        self.conn.commit()

    def weekly_minutes_for_current_workweek(self, task_id: int) -> int:
        # Sum manual minutes + session overlap minutes within the current workweek window
        now_local = to_local(now_utc())
        pk = period_key_workweek(now_local)

        # We compute overlap using split_interval_by_workweek per session.
        rows = self.conn.execute(
            "SELECT start_utc, end_utc, manual_minutes FROM sessions WHERE task_id=?",
            (task_id,),
        ).fetchall()

        total = 0
        for r in rows:
            manual = int(r["manual_minutes"])
            if manual > 0:
                # manual minutes count if in current workweek period (by start_utc local)
                start = datetime.fromisoformat(r["start_utc"]).replace(tzinfo=timezone.utc)
                if period_key_workweek(to_local(start)) == pk:
                    total += manual
                continue

            start = datetime.fromisoformat(r["start_utc"]).replace(tzinfo=timezone.utc)
            end_iso = r["end_utc"]
            end = now_utc() if end_iso is None else datetime.fromisoformat(end_iso).replace(tzinfo=timezone.utc)

            if period_key_workweek(to_local(start)) != pk:
                continue

            total += split_interval_by_workweek(start, end)

        return total

    # ---------- Completion ----------
    def is_completed_for_current_period(self, task_id: int) -> bool:
        now_local = to_local(now_utc())
        pk = period_key_workweek(now_local)
        r = self.conn.execute(
            "SELECT 1 FROM completions WHERE task_id=? AND period_key=?",
            (task_id, pk),
        ).fetchone()
        return bool(r)

    def mark_complete_for_current_period(self, task_id: int) -> None:
        now_local = to_local(now_utc())
        pk = period_key_workweek(now_local)
        self.conn.execute(
            "INSERT OR IGNORE INTO completions(task_id, period_key, completed_utc) VALUES(?,?,?)",
            (task_id, pk, now_utc().isoformat()),
        )
        self.conn.commit()

    def clear_completion_for_current_period(self, task_id: int) -> None:
        now_local = to_local(now_utc())
        pk = period_key_workweek(now_local)
        self.conn.execute(
            "DELETE FROM completions WHERE task_id=? AND period_key=?",
            (task_id, pk),
        )
        self.conn.commit()

    def delete_sessions_for_current_workweek(self, task_id: int) -> None:
        now_local = to_local(now_utc())
        pk = period_key_workweek(now_local)

        rows = self.conn.execute(
            "SELECT id, start_utc, manual_minutes FROM sessions WHERE task_id=?",
            (task_id,),
        ).fetchall()

        for r in rows:
            start = datetime.fromisoformat(r["start_utc"]).replace(tzinfo=timezone.utc)
            if period_key_workweek(to_local(start)) == pk:
                self.conn.execute("DELETE FROM sessions WHERE id=?", (r["id"],))

        self.conn.commit()

