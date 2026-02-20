from __future__ import annotations
from pathlib import Path
from PySide6.QtGui import QIcon


def resource_path(*parts: str) -> Path:
    # Works in dev and in PyInstaller
    import sys
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base = Path(__file__).resolve().parent
    return base.joinpath(*parts)


def tray_icon() -> QIcon:
    p = resource_path("assets", "tray.png")
    return QIcon(str(p))
