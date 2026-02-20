# Offline Reminder (macOS + Windows)

A tiny offline tray/menu-bar reminder utility with:
- Weekly time quota tasks (sessions + manual minutes)
- Complete-once-per-workweek tasks
- Persistent snooze / skip-today
- Start-at-login toggle (Windows registry Run key, macOS LaunchAgent)

## Requirements
- Python 3.10+ recommended (3.11/3.12 fine)
- pip3
- macOS or Windows

## Run locally

### 1) Create venv and install deps

#### macOS
```bash
python3 -m venv .venv
source .venv/bin/activate
pip3 install -r requirements.txt
