from __future__ import annotations

import sys

from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication

from .database import Database
from .paths import APP_NAME, backups_dir, database_path, resource_path
from .style import APP_STYLE
from .ui import MainWindow


def run() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("BonusDesk")
    app.setWindowIcon(QIcon(str(resource_path("assets/bonusdesk.ico"))))
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(APP_STYLE)

    db = Database(database_path())
    try:
        db.backup(backups_dir())
    except OSError:
        pass
    window = MainWindow(db)
    window.show()
    return app.exec()
