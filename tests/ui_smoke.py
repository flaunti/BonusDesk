from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from PySide6.QtWidgets import QApplication, QLabel

from bonusdesk.database import Database
from bonusdesk.parser import parse_report
from bonusdesk.style import APP_STYLE
from bonusdesk.ui import MainWindow


SAMPLE = """
Отчёт на премию
Имя фамилия
Test Employee
Ваш Static ID.
100001
Ваш основной отдел:
AD
Ваш дополнительный отдел:
Отсутствует.
Подача 1 зеленого эфира (кол-во):
21
Подача 1 зеленого эфира (док-ва):
https://example.test/proof/one
https://example.test/proof/two
"""


def main() -> int:
    output = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else None
    app = QApplication([])
    app.setStyleSheet(APP_STYLE)
    with tempfile.TemporaryDirectory() as tmp:
        db = Database(Path(tmp) / "bonusdesk.db")
        db.set_setting("update_check_enabled", "0")
        week_id = int(db.current_week()["id"])
        db.add_report(week_id, parse_report(SAMPLE))
        window = MainWindow(db)
        window.resize(1380, 860)
        window.show()
        app.processEvents()
        price_control = window.review_page.row_controls[0]["price"]
        evidence_labels = window.review_page.work_table.cellWidget(0, 5).findChildren(QLabel)
        assert len(evidence_labels) == 2
        assert all(label.openExternalLinks() for label in evidence_labels)
        window.navigate(2)
        window.bulk_page.source.setPlainText(
            "Alex Example | 100001 | Director | Example Org\n"
            "Alex Example | 100001 | 15 | 100.000$\n"
            "Edward Saint | 46604 | 14 | 100.000$\n"
            "Итоговая сумма: 200.000$"
        )
        window.bulk_page.parse()
        assert len(window.bulk_page.result.payments) == 2
        assert window.bulk_page.result.total == 200_000
        assert window.bulk_page.export_text().splitlines()[1] == "100001;100000;Премия GOV"
        window.navigate(0)

        class FakeWheelEvent:
            ignored = False

            def ignore(self):
                self.ignored = True

        wheel_event = FakeWheelEvent()
        original_price = price_control.value()
        price_control.wheelEvent(wheel_event)
        assert price_control.value() == original_price
        assert wheel_event.ignored
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            if not window.grab().save(str(output)):
                raise RuntimeError("Could not save UI screenshot")
            for index, suffix in ((1, "summary"), (2, "bulk"), (3, "prices"), (4, "periods"), (5, "settings")):
                if index == 1:
                    window.review_page.row_controls[0]["accepted"].setValue(20)
                window.navigate(index)
                app.processEvents()
                if index == 1:
                    _, saved_items = db.report(window.review_page.current_report_id)
                    assert saved_items[0]["accepted_count"] == 20
                page_output = output.with_name(f"{output.stem}_{suffix}{output.suffix}")
                if not window.grab().save(str(page_output)):
                    raise RuntimeError(f"Could not save {suffix} screenshot")
        window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
