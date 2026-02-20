from __future__ import annotations

import sys
from pathlib import Path

APP_ID = "OfflineReminder"
PLIST_NAME = "com.offlinereminder.agent.plist"
RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"


# ============================================================
# Public API
# ============================================================

def enable_start_at_login(enable: bool) -> None:
    """
    Enable or disable start-at-login for current user.
    """
    if sys.platform.startswith("win"):
        _win_set_run_key(enable)
    elif sys.platform == "darwin":
        _mac_set_launch_agent(enable)
    else:
        # Linux not implemented for this project
        pass


def is_start_at_login_enabled() -> bool:
    if sys.platform.startswith("win"):
        return _win_is_run_key_set()
    elif sys.platform == "darwin":
        return _mac_launch_agent_exists()
    return False


# ============================================================
# Command Resolution
# ============================================================

def app_command_for_autostart() -> list[str]:
    """
    Returns the command used for autostart.

    Packaged mode (PyInstaller):
        sys.executable is the built executable.

    Dev mode:
        macOS -> python3 run.py
        Windows -> python run.py
    """
    # Packaged build
    if getattr(sys, "frozen", False):
        return [sys.executable]

    run_py = str(_project_root() / "run.py")

    if sys.platform == "darwin":
        return ["python3", run_py]

    # Windows dev mode
    return ["python", run_py]


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _quote_if_needed(s: str) -> str:
    if " " in s:
        return f'"{s}"'
    return s


# ============================================================
# Windows Implementation
# ============================================================

def _win_set_run_key(enable: bool) -> None:
    import winreg  # type: ignore

    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        RUN_KEY_PATH,
        0,
        winreg.KEY_ALL_ACCESS,
    ) as key:

        if enable:
            cmd = app_command_for_autostart()
            cmd_str = " ".join(_quote_if_needed(c) for c in cmd)
            winreg.SetValueEx(key, APP_ID, 0, winreg.REG_SZ, cmd_str)
        else:
            try:
                winreg.DeleteValue(key, APP_ID)
            except FileNotFoundError:
                pass


def _win_is_run_key_set() -> bool:
    import winreg  # type: ignore

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY_PATH,
            0,
            winreg.KEY_READ,
        ) as key:
            winreg.QueryValueEx(key, APP_ID)
            return True
    except FileNotFoundError:
        return False


# ============================================================
# macOS Implementation
# ============================================================

def _mac_launch_agents_dir() -> Path:
    return Path.home() / "Library" / "LaunchAgents"


def _mac_plist_path() -> Path:
    return _mac_launch_agents_dir() / PLIST_NAME


def _mac_set_launch_agent(enable: bool) -> None:
    d = _mac_launch_agents_dir()
    d.mkdir(parents=True, exist_ok=True)

    plist = _mac_plist_path()

    if not enable:
        if plist.exists():
            plist.unlink()
        return

    cmd = app_command_for_autostart()

    program_args = "\n".join(
        f"    <string>{_xml_escape(c)}</string>" for c in cmd
    )

    contents = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>{PLIST_NAME}</string>
  <key>ProgramArguments</key>
  <array>
{program_args}
  </array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><false/>
</dict>
</plist>
"""
    plist.write_text(contents, encoding="utf-8")


def _mac_launch_agent_exists() -> bool:
    return _mac_plist_path().exists()


def _xml_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
         .replace("'", "&apos;")
    )
