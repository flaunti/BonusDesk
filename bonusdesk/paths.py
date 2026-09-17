from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


APP_NAME = "BonusDesk"


def resource_path(relative: str) -> Path:
    """Resolve bundled assets both from source and from a PyInstaller build."""
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return root / relative


def app_data_dir() -> Path:
    if sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    path = root / "BonusDesk"
    path.mkdir(parents=True, exist_ok=True)
    return path


def database_path() -> Path:
    path = app_data_dir() / "data" / "bonusdesk.db"
    if not path.exists():
        # Keep data created by earlier builds when the product name changes.
        legacy_root = app_data_dir().parent / "".join(("WN", "BonusChecker"))
        legacy_path = legacy_root / "data" / "_".join(("wn", "bonus.db"))
        if legacy_path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(legacy_path, path)
    return path


def exports_dir() -> Path:
    path = app_data_dir() / "exports"
    path.mkdir(parents=True, exist_ok=True)
    return path


def backups_dir() -> Path:
    path = app_data_dir() / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path
