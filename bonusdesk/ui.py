from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import QDate, QEvent, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QColor, QCloseEvent, QDesktopServices, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QSizePolicy,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .database import Database, DuplicateReportError
from .dialogs import ImportReportDialog
from .bulk_page import BulkListPage
from .parser import extract_urls
from .paths import APP_NAME, backups_dir, exports_dir, resource_path
from .updater import CURRENT_VERSION, REPOSITORY_URL, UpdateChecker, UpdateInfo
from .widgets import Card, EvidenceLinks, NoWheelSpinBox, StatCard, money, page_header


STATUS_LABELS = {"pending": "Ожидает проверки", "approved": "Засчитано", "rejected": "Не учитывается"}
STATUS_MARKS = {"pending": "●", "approved": "✓", "rejected": "×"}


def notify(parent, title: str, text: str) -> None:
    QMessageBox.information(parent, title, text)


class CreateWeekDialog(QDialog):
    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Новый отчётный период")
        self.setModal(True)
        self.setMinimumWidth(470)

        current = db.current_week()
        default_start = date.fromisoformat(current["date_end"]) + timedelta(days=1)
        default_end = default_start + timedelta(days=6)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 22, 22, 18)
        root.setSpacing(16)
        title = QLabel("Создать отчётный период")
        title.setObjectName("pageTitle")
        hint = QLabel(
            "Укажи точные даты. Текущий период будет перенесён в архив, "
            "а все новые отчёты начнут попадать в созданный период."
        )
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(hint)

        form = QFormLayout()
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)
        self.start_date = QDateEdit(QDate(default_start.year, default_start.month, default_start.day))
        self.end_date = QDateEdit(QDate(default_end.year, default_end.month, default_end.day))
        for editor in (self.start_date, self.end_date):
            editor.setCalendarPopup(True)
            editor.setDisplayFormat("dd.MM.yyyy")
            editor.setMinimumWidth(190)
        self.start_date.dateChanged.connect(self._start_changed)
        form.addRow("Начало периода", self.start_date)
        form.addRow("Окончание периода", self.end_date)
        root.addLayout(form)

        self.preview = QLabel()
        self.preview.setObjectName("periodPreview")
        self.preview.setWordWrap(True)
        root.addWidget(self.preview)
        self.start_date.dateChanged.connect(self._update_preview)
        self.end_date.dateChanged.connect(self._update_preview)
        self._update_preview()

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        buttons.button(QDialogButtonBox.Ok).setText("Создать период")
        buttons.button(QDialogButtonBox.Ok).setObjectName("primary")
        buttons.button(QDialogButtonBox.Cancel).setText("Отмена")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _start_changed(self, value: QDate) -> None:
        self.end_date.setMinimumDate(value)
        self.end_date.setDate(value.addDays(6))

    def _update_preview(self, _value=None) -> None:
        start = self.start_date.date().toString("dd.MM.yyyy")
        end = self.end_date.date().toString("dd.MM.yyyy")
        days = self.start_date.date().daysTo(self.end_date.date()) + 1
        self.preview.setText(f"Новый период:  {start} — {end}   ·   {days} дн.")

    def dates(self) -> tuple[date, date]:
        return self.start_date.date().toPython(), self.end_date.date().toPython()


class ReviewPage(QWidget):
    data_changed = Signal()

    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.week_id = int(db.current_week()["id"])
        self.current_report_id: int | None = None
        self.row_controls: list[dict] = []
        self.current_comment = ""
        self._dirty = False

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 22)
        root.setSpacing(16)
        week = db.current_week()
        header, header_layout = page_header("Проверка отчётов", f"Активный период: {week['title']}")
        self.week_caption = header.findChild(QLabel, "pageSubtitle")
        import_button = QPushButton("Импортировать из буфера")
        import_button.setObjectName("primary")
        import_button.clicked.connect(self.import_clipboard)
        manual_button = QPushButton("Добавить вручную")
        manual_button.clicked.connect(self.add_manual)
        header_layout.addWidget(manual_button)
        header_layout.addWidget(import_button)
        root.addWidget(header)

        self.bulk_bar = Card(margins=(14, 10, 14, 10))
        bulk_actions = QHBoxLayout()
        bulk_title = QLabel("Массовые действия")
        bulk_title.setObjectName("sectionTitle")
        self.bulk_count = QLabel("Отчётов: 0")
        self.bulk_count.setObjectName("muted")
        self.approve_all_button = QPushButton("Засчитать все")
        self.approve_all_button.setObjectName("success")
        self.approve_all_button.clicked.connect(self.approve_all)
        self.reset_all_button = QPushButton("Вернуть на проверку все")
        self.reset_all_button.clicked.connect(self.reset_all)
        self.delete_all_button = QPushButton("Удалить все")
        self.delete_all_button.setObjectName("danger")
        self.delete_all_button.clicked.connect(self.delete_all)
        bulk_actions.addWidget(bulk_title)
        bulk_actions.addWidget(self.bulk_count)
        bulk_actions.addStretch(1)
        bulk_actions.addWidget(self.reset_all_button)
        bulk_actions.addWidget(self.delete_all_button)
        bulk_actions.addWidget(self.approve_all_button)
        self.bulk_bar.box.addLayout(bulk_actions)
        root.addWidget(self.bulk_bar)

        content = QHBoxLayout()
        content.setSpacing(16)
        left = Card(margins=(12, 12, 12, 12))
        left.setMinimumWidth(270)
        left.setMaximumWidth(320)
        search = QLineEdit()
        search.setPlaceholderText("Поиск по имени или Static ID")
        search.textChanged.connect(self._filter)
        self.search = search
        left.box.addWidget(search)
        self.report_list = QListWidget()
        self.report_list.currentItemChanged.connect(self._selected)
        left.box.addWidget(self.report_list, 1)
        content.addWidget(left)

        self.detail = Card()
        self.detail.setMinimumWidth(720)
        content.addWidget(self.detail, 1)
        root.addLayout(content, 1)
        self._build_detail()
        self.refresh()

    def _build_detail(self) -> None:
        top = QHBoxLayout()
        person = QVBoxLayout()
        self.person_name = QLabel("Выбери отчёт слева")
        self.person_name.setObjectName("sectionTitle")
        self.person_meta = QLabel("")
        self.person_meta.setObjectName("muted")
        person.addWidget(self.person_name)
        person.addWidget(self.person_meta)
        top.addLayout(person)
        top.addStretch(1)
        self.status_label = QLabel("")
        top.addWidget(self.status_label)
        self.detail.box.addLayout(top)

        self.warning = QLabel("")
        self.warning.setObjectName("warning")
        self.warning.setWordWrap(True)
        self.warning.hide()
        self.detail.box.addWidget(self.warning)

        self.work_table = QTableWidget(0, 6)
        self.work_table.setHorizontalHeaderLabels(["Вид работы", "Заявлено", "Принято", "Цена", "Сумма", "Доказательства"])
        header = self.work_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for column in (1, 2, 3, 4, 5):
            header.setSectionResizeMode(column, QHeaderView.Fixed)
        self.work_table.setColumnWidth(1, 84)
        self.work_table.setColumnWidth(2, 90)
        self.work_table.setColumnWidth(3, 112)
        self.work_table.setColumnWidth(4, 105)
        self.work_table.setColumnWidth(5, 160)
        self.work_table.verticalHeader().setVisible(False)
        self.work_table.verticalHeader().setDefaultSectionSize(46)
        self.work_table.setSelectionMode(QAbstractItemView.NoSelection)
        self.work_table.setMinimumHeight(230)
        self.detail.box.addWidget(self.work_table, 1)

        totals = QHBoxLayout()
        self.source_name = QLabel("")
        self.source_name.setObjectName("muted")
        self.source_name.setWordWrap(True)
        totals.addWidget(self.source_name, 1)
        money_box = QVBoxLayout()
        money_title = QLabel("Итого по отчёту")
        money_title.setObjectName("muted")
        self.total_label = QLabel("0 $")
        self.total_label.setObjectName("money")
        self.limit_hint = QLabel("Недельный лимит: 150 000 $")
        self.limit_hint.setObjectName("muted")
        money_box.addWidget(money_title, alignment=Qt.AlignRight)
        money_box.addWidget(self.total_label, alignment=Qt.AlignRight)
        money_box.addWidget(self.limit_hint, alignment=Qt.AlignRight)
        totals.addLayout(money_box)
        self.detail.box.addLayout(totals)

        actions = QHBoxLayout()
        self.more_button = QPushButton("Ещё  ⋯")
        more_menu = self.more_button.menu() or None
        if more_menu is None:
            from PySide6.QtWidgets import QMenu

            more_menu = QMenu(self.more_button)
            self.more_button.setMenu(more_menu)
        more_menu.addAction("Вернуть на проверку", lambda: self.set_status("pending"))
        more_menu.addSeparator()
        more_menu.addAction("Удалить отчёт", self.delete_current)
        self.reject_button = QPushButton("Не учитывать")
        self.reject_button.setObjectName("danger")
        self.reject_button.clicked.connect(lambda: self.set_status("rejected"))
        self.approve_button = QPushButton("Засчитать отчёт")
        self.approve_button.setObjectName("success")
        self.approve_button.clicked.connect(lambda: self.set_status("approved"))
        actions.addStretch(1)
        actions.addWidget(self.more_button)
        actions.addWidget(self.reject_button)
        actions.addWidget(self.approve_button)
        self.detail.box.addLayout(actions)
        self._set_detail_enabled(False)

    def _set_detail_enabled(self, enabled: bool) -> None:
        for widget in (self.work_table, self.more_button, self.reject_button, self.approve_button):
            widget.setEnabled(enabled)

    def refresh(self, keep_id: int | None = None) -> None:
        self.persist_if_dirty()
        week = self.db.current_week()
        new_week_id = int(week["id"])
        if new_week_id != self.week_id:
            self.week_id = new_week_id
            self.current_report_id = None
            keep_id = None
        if self.week_caption:
            self.week_caption.setText(f"Активный период: {week['title']}")
        keep_id = keep_id if keep_id is not None else self.current_report_id
        self.report_list.clear()
        selected_item = None
        reports = self.db.reports(self.week_id)
        pending_count = sum(1 for report in reports if report["status"] == "pending")
        self.bulk_count.setText(f"Отчётов: {len(reports)}  ·  ожидают: {pending_count}")
        for button in (self.approve_all_button, self.reset_all_button, self.delete_all_button):
            button.setEnabled(bool(reports))
        for report in reports:
            item = QListWidgetItem(
                f"{STATUS_MARKS[report['status']]}  {report['employee_name']}\n"
                f"    #{report['static_id']}  ·  {money(report['raw_amount'])}"
            )
            item.setData(Qt.UserRole, int(report["id"]))
            item.setData(Qt.UserRole + 1, f"{report['employee_name']} {report['static_id']}".casefold())
            if report["status"] == "approved":
                item.setForeground(QColor("#0e6f68"))
            elif report["status"] == "rejected":
                item.setForeground(QColor("#b8423a"))
            self.report_list.addItem(item)
            if int(report["id"]) == keep_id:
                selected_item = item
        if selected_item:
            self.report_list.setCurrentItem(selected_item)
        elif self.report_list.count():
            self.report_list.setCurrentRow(0)
        else:
            self.current_report_id = None
            self.person_name.setText("Отчётов пока нет")
            self.person_meta.setText("Скопируй текст отчёта и нажми «Импортировать из буфера».")
            self.work_table.setRowCount(0)
            self.warning.hide()
            self._set_detail_enabled(False)
        self._filter(self.search.text())

    def _filter(self, text: str) -> None:
        needle = text.strip().casefold()
        for index in range(self.report_list.count()):
            item = self.report_list.item(index)
            item.setHidden(bool(needle and needle not in item.data(Qt.UserRole + 1)))

    def _selected(self, current: QListWidgetItem | None, _previous: QListWidgetItem | None) -> None:
        if not current:
            return
        report_id = int(current.data(Qt.UserRole))
        if self.current_report_id != report_id:
            self.persist_if_dirty()
        self.load_report(report_id)

    def load_report(self, report_id: int) -> None:
        report, items = self.db.report(report_id)
        if not report:
            return
        self.current_report_id = report_id
        self.person_name.setText(report["employee_name"])
        departments = " / ".join(x for x in (report["primary_department"], report["secondary_department"]) if x and "отсутств" not in x.casefold())
        self.person_meta.setText(f"Static ID: {report['static_id']}   ·   Отдел: {departments or 'не указан'}   ·   Отчёт #{report_id}")
        self.status_label.setText(STATUS_LABELS[report["status"]])
        self.status_label.setStyleSheet(
            "font-weight:700; padding:6px 10px; border-radius:8px; "
            + ("color:#0e6f68; background:#e8f7f5;" if report["status"] == "approved" else "color:#245e9e; background:#eaf3fe;" if report["status"] == "pending" else "color:#b8423a; background:#fdecea;")
        )
        self.current_comment = report["reviewer_comment"]
        # Recreate rows from scratch so cell widgets from a previous selection
        # cannot remain layered over the new controls after a window resize.
        self.work_table.setRowCount(0)
        self.work_table.setRowCount(len(items))
        self.row_controls = []
        work_types = self.db.work_types(enabled_only=True)
        for row, item in enumerate(items):
            combo = QComboBox()
            combo.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            combo.addItem("Не сопоставлено", None)
            for work in work_types:
                combo.addItem(f"{work['department']} · {work['name']}", int(work["id"]))
                combo.setItemData(combo.count() - 1, int(work["price"]), Qt.UserRole + 1)
            match_index = combo.findData(item["work_type_id"])
            combo.setCurrentIndex(max(0, match_index))
            combo.setToolTip(f"Из отчёта: {item['raw_name']}")
            self.work_table.setCellWidget(row, 0, combo)

            claimed = QTableWidgetItem(str(item["claimed_count"]))
            claimed.setTextAlignment(Qt.AlignCenter)
            claimed.setFlags(claimed.flags() & ~Qt.ItemIsEditable)
            self.work_table.setItem(row, 1, claimed)

            accepted = NoWheelSpinBox()
            accepted.setRange(0, max(0, int(item["claimed_count"])))
            accepted.setValue(int(item["accepted_count"]))
            accepted.setMaximumWidth(82)
            self.work_table.setCellWidget(row, 2, accepted)

            price = NoWheelSpinBox()
            price.setRange(0, 10_000_000)
            price.setSingleStep(500)
            price.setSuffix(" $")
            price.setValue(int(item["price_snapshot"]))
            price.setMaximumWidth(132)
            self.work_table.setCellWidget(row, 3, price)

            subtotal = QTableWidgetItem("")
            subtotal.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            subtotal.setFlags(subtotal.flags() & ~Qt.ItemIsEditable)
            self.work_table.setItem(row, 4, subtotal)

            urls = extract_urls(item["evidence_url"])
            evidence = EvidenceLinks(urls)
            self.work_table.setCellWidget(row, 5, evidence)
            self.work_table.setRowHeight(row, max(48, 27 * max(1, len(urls)) + 10))
            controls = {"id": int(item["id"]), "combo": combo, "accepted": accepted, "price": price, "subtotal": subtotal, "raw_name": item["raw_name"], "evidence": item["evidence_url"]}
            self.row_controls.append(controls)
            accepted.valueChanged.connect(self._control_changed)
            price.valueChanged.connect(self._control_changed)
            combo.currentIndexChanged.connect(lambda _index, controls=controls: self._work_changed(controls))

        warnings: list[str] = []
        unmapped = [item["raw_name"] for item in items if item["work_type_id"] is None]
        if unmapped:
            warnings.append("Не сопоставлено с прайсом: " + ", ".join(unmapped))
        duplicates = self.db.duplicate_evidence(report_id)
        if duplicates:
            seen = {(row["static_id"], row["report_id"]) for row in duplicates}
            warnings.append("Повторно использованные доказательства: " + ", ".join(f"Static {static_id}, отчёт #{other_id}" for static_id, other_id in seen))
        without_evidence = [item["raw_name"] for item in items if not item["evidence_url"]]
        if without_evidence:
            warnings.append("Нет ссылки на доказательства: " + ", ".join(without_evidence))
        if warnings:
            self.warning.setText("⚠  " + "\n⚠  ".join(warnings))
            self.warning.show()
        else:
            self.warning.hide()
        self.source_name.setText("Исходные названия:\n" + " · ".join(item["raw_name"] for item in items))
        self._set_detail_enabled(True)
        self.recalculate()
        self._dirty = False

    def _work_changed(self, controls: dict) -> None:
        index = controls["combo"].currentIndex()
        default_price = controls["combo"].itemData(index, Qt.UserRole + 1)
        if default_price is not None:
            controls["price"].setValue(int(default_price))
        self._control_changed()

    def _control_changed(self, _value=None) -> None:
        self._dirty = True
        self.recalculate()

    def recalculate(self) -> None:
        total = 0
        for controls in self.row_controls:
            subtotal = controls["accepted"].value() * controls["price"].value()
            total += subtotal
            controls["subtotal"].setText(money(subtotal))
        self.total_label.setText(money(total))
        limit = int(self.db.setting("weekly_limit", "150000"))
        self.limit_hint.setText(f"Недельный лимит: {money(limit)}")
        self.total_label.setStyleSheet("font-size:27px; font-weight:800; color:%s;" % ("#c56a19" if total > limit else "#2563eb"))

    def _payload(self) -> list[dict]:
        return [
            {
                "id": controls["id"],
                "work_type_id": controls["combo"].currentData(),
                "accepted_count": controls["accepted"].value(),
                "price": controls["price"].value(),
            }
            for controls in self.row_controls
        ]

    def persist_if_dirty(self) -> None:
        if self.current_report_id is None or not self._dirty:
            return
        self.db.update_report(self.current_report_id, self._payload(), self.current_comment)
        self._dirty = False
        self.data_changed.emit()

    def set_status(self, status: str) -> None:
        if self.current_report_id is None:
            return
        if status == "approved":
            problems = []
            for controls in self.row_controls:
                if controls["accepted"].value() > 0 and controls["combo"].currentData() is None:
                    problems.append(f"«{controls['raw_name']}» не сопоставлено с прайсом")
                if controls["accepted"].value() > 0 and controls["price"].value() <= 0:
                    problems.append(f"для «{controls['raw_name']}» не указана цена")
            if problems:
                QMessageBox.warning(self, "Нельзя одобрить", "Исправь перед одобрением:\n\n• " + "\n• ".join(problems))
                return
        self.db.update_report(self.current_report_id, self._payload(), self.current_comment)
        self._dirty = False
        self.db.set_report_status(self.current_report_id, status, self.current_comment)
        self.refresh(self.current_report_id)
        self.data_changed.emit()

    def delete_current(self) -> None:
        if self.current_report_id is None:
            return
        answer = QMessageBox.question(self, "Удалить отчёт?", "Отчёт и его расчёт будут удалены. Продолжить?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer == QMessageBox.Yes:
            self.db.delete_report(self.current_report_id)
            self.current_report_id = None
            self.refresh()
            self.data_changed.emit()

    def approve_all(self) -> None:
        reports = self.db.reports(self.week_id)
        if not reports:
            return
        self.persist_if_dirty()
        answer = QMessageBox.question(
            self,
            "Засчитать все отчёты?",
            f"Будут засчитаны все корректные отчёты активного периода — всего {len(reports)}.\n\n"
            "Отчёты с несопоставленными работами или нулевой ценой останутся на проверке.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        approved, invalid_ids = self.db.approve_week_reports(self.week_id)
        self.refresh(self.current_report_id)
        self.data_changed.emit()
        if invalid_ids:
            QMessageBox.warning(
                self,
                "Часть отчётов требует проверки",
                f"Засчитано: {approved}.\nОставлено на проверке: {len(invalid_ids)}.\n\n"
                "Проверь сопоставление работ и цены в оставшихся отчётах.",
            )
        else:
            notify(self, "Готово", f"Засчитано отчётов: {approved}.")

    def reset_all(self) -> None:
        reports = self.db.reports(self.week_id)
        if not reports:
            return
        answer = QMessageBox.question(
            self,
            "Вернуть все отчёты на проверку?",
            f"Статус всех отчётов активного периода ({len(reports)}) изменится на «Ожидает проверки».\n"
            "Принятые количества и цены сохранятся.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            count = self.db.reset_week_reports(self.week_id)
            self.refresh(self.current_report_id)
            self.data_changed.emit()
            notify(self, "Готово", f"Возвращено на проверку: {count}.")

    def delete_all(self) -> None:
        reports = self.db.reports(self.week_id)
        if not reports:
            return
        week = self.db.current_week()
        answer = QMessageBox.question(
            self,
            "Удалить все отчёты?",
            f"Будут безвозвратно удалены все отчёты периода {week['title']} — всего {len(reports)}.\n\n"
            "Сам отчётный период останется. Продолжить?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer == QMessageBox.Yes:
            count = self.db.delete_week_reports(self.week_id)
            self.current_report_id = None
            self.refresh()
            self.data_changed.emit()
            notify(self, "Отчёты удалены", f"Удалено отчётов: {count}.")

    def import_clipboard(self) -> None:
        dialog = ImportReportDialog(QApplication.clipboard().text(), parent=self)
        self._run_import(dialog)

    def add_manual(self) -> None:
        self._run_import(ImportReportDialog(manual=True, parent=self))

    def _run_import(self, dialog: ImportReportDialog) -> None:
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            report_id = self.db.add_report(self.week_id, dialog.result_report())
        except DuplicateReportError as exc:
            QMessageBox.warning(self, "Дубликат", str(exc))
            return
        self.refresh(report_id)
        self.data_changed.emit()


class SummaryPage(QWidget):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.week_id = int(db.current_week()["id"])
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 22)
        root.setSpacing(16)
        week = db.current_week()
        header, actions = page_header("Итоги недели", f"Активный период: {week['title']}")
        self.week_caption = header.findChild(QLabel, "pageSubtitle")
        copy_button = QPushButton("Скопировать итог")
        copy_button.clicked.connect(self.copy_export)
        export_button = QPushButton("Экспорт TXT")
        export_button.setObjectName("primary")
        export_button.clicked.connect(self.save_export)
        actions.addWidget(copy_button)
        actions.addWidget(export_button)
        root.addWidget(header)
        stat_row = QHBoxLayout()
        self.stat_people = StatCard("Сотрудников", "0")
        self.stat_raw = StatCard("Начислено по работам", "0 $")
        self.stat_payout = StatCard("К выплате", "0 $", accent=True)
        self.stat_cut = StatCard("Срезано лимитом", "0 $")
        for card in (self.stat_people, self.stat_raw, self.stat_payout, self.stat_cut):
            stat_row.addWidget(card)
        root.addLayout(stat_row)
        card = Card()
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Static ID", "Сотрудник", "Отчётов", "По работам", "К выплате", "Лимит"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for col in (0, 2, 3, 4, 5):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(46)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        card.box.addWidget(self.table)
        root.addWidget(card, 1)
        self.empty_hint = QLabel("В экспорт попадают только одобренные отчёты. Несколько отчётов одного Static ID суммируются, затем применяется недельный лимит.")
        self.empty_hint.setObjectName("muted")
        self.empty_hint.setWordWrap(True)
        root.addWidget(self.empty_hint)
        self.refresh()

    def refresh(self) -> None:
        week = self.db.current_week()
        self.week_id = int(week["id"])
        if self.week_caption:
            self.week_caption.setText(f"Активный период: {week['title']}")
        rows = self.db.aggregates(self.week_id)
        limit = int(self.db.setting("weekly_limit", "150000"))
        raw_total = sum(int(row["raw_amount"]) for row in rows)
        payout_total = sum(int(row["payout"]) for row in rows)
        self.stat_people.value_label.setText(str(len(rows)))
        self.stat_raw.value_label.setText(money(raw_total))
        self.stat_payout.value_label.setText(money(payout_total))
        self.stat_cut.value_label.setText(money(raw_total - payout_total))
        self.table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            values = [row["static_id"], row["employee_name"], str(row["reports_count"]), money(row["raw_amount"]), money(row["payout"]), "Достигнут" if row["raw_amount"] > limit else "—"]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in (2, 3, 4, 5):
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if column == 5 and row["raw_amount"] > limit:
                    item.setForeground(QColor("#c56a19"))
                self.table.setItem(index, column, item)

    def copy_export(self) -> None:
        if not self.db.aggregates(self.week_id):
            QMessageBox.warning(self, "Экспорт пуст", "Сначала засчитай хотя бы один отчёт.")
            return
        text = self.db.export_text(self.week_id)
        QApplication.clipboard().setText(text)
        notify(self, "Скопировано", "Итоговый список скопирован в буфер обмена.")

    def save_export(self) -> None:
        if not self.db.aggregates(self.week_id):
            QMessageBox.warning(self, "Экспорт пуст", "Сначала засчитай хотя бы один отчёт.")
            return
        text = self.db.export_text(self.week_id)
        week = self.db.current_week()
        suggested = exports_dir() / f"premium_{week['date_end']}.txt"
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить премии", str(suggested), "Текстовый файл (*.txt)")
        if not path:
            return
        Path(path).write_text(text + "\n", encoding="utf-8-sig")
        notify(self, "Экспорт готов", f"Файл сохранён:\n{path}")


class PricePage(QWidget):
    data_changed = Signal()

    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 22)
        root.setSpacing(16)
        header, actions = page_header("Виды работ", "Настрой названия, цены и варианты написания для автоматического сопоставления.")
        add = QPushButton("+ Добавить работу")
        add.clicked.connect(lambda: self.add_row())
        remove = QPushButton("Удалить выбранную")
        remove.setObjectName("danger")
        remove.clicked.connect(self.remove_selected)
        save = QPushButton("Сохранить изменения")
        save.setObjectName("primary")
        save.clicked.connect(self.save)
        actions.addWidget(add)
        actions.addWidget(remove)
        actions.addWidget(save)
        root.addWidget(header)
        card = Card()
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Отдел", "Название", "Цена за 1", "Алиасы через запятую", "Активно"])
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.Fixed)
        header_view.setSectionResizeMode(1, QHeaderView.Fixed)
        header_view.setSectionResizeMode(2, QHeaderView.Fixed)
        header_view.setSectionResizeMode(3, QHeaderView.Stretch)
        header_view.setSectionResizeMode(4, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 82)
        self.table.setColumnWidth(1, 330)
        self.table.setColumnWidth(2, 120)
        self.table.setColumnWidth(4, 88)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(True)
        self.table.verticalHeader().setDefaultSectionSize(46)
        card.box.addWidget(self.table)
        root.addWidget(card, 1)
        self.refresh()

    def refresh(self) -> None:
        rows = self.db.work_types()
        self.table.setRowCount(0)
        for row in rows:
            self.add_row(row)
        if rows:
            self.table.setCurrentCell(0, 0)
            self.table.scrollToTop()

    def add_row(self, row=None) -> None:
        index = self.table.rowCount()
        self.table.insertRow(index)
        department = QLineEdit(row["department"] if row else "")
        department.setMaximumWidth(85)
        name = QLineEdit(row["name"] if row else "")
        name.setProperty("work_type_id", int(row["id"]) if row else None)
        name.setCursorPosition(0)
        price = NoWheelSpinBox()
        price.setRange(0, 10_000_000)
        price.setSingleStep(500)
        price.setSuffix(" $")
        price.setValue(int(row["price"]) if row else 0)
        aliases = QLineEdit(", ".join(json.loads(row["aliases"] or "[]")) if row else "")
        aliases.setCursorPosition(0)
        enabled = QCheckBox()
        enabled.setChecked(bool(row["enabled"]) if row else True)
        for column, widget in enumerate((department, name, price, aliases, enabled)):
            self.table.setCellWidget(index, column, widget)
            widget.setProperty("price_row", index)
            widget.installEventFilter(self)
            if isinstance(widget, NoWheelSpinBox):
                widget.lineEdit().setProperty("price_row", index)
                widget.lineEdit().installEventFilter(self)
        if row is None:
            self.table.setCurrentCell(index, 0)
            self.table.scrollToBottom()

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 - Qt API name
        if event.type() == QEvent.MouseButtonPress:
            row = watched.property("price_row")
            if row is not None and 0 <= int(row) < self.table.rowCount():
                self.table.setCurrentCell(int(row), 0)
        return super().eventFilter(watched, event)

    def remove_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Строка не выбрана", "Выбери строку прайса, которую нужно удалить.")
            return
        name = self.table.cellWidget(row, 1).text().strip() or "новая работа"
        answer = QMessageBox.question(self, "Удалить строку?", f"Убрать из прайса «{name}»?\n\nИзменение применится после сохранения прайса.", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer == QMessageBox.Yes:
            self.table.removeRow(row)
            self._renumber_rows()

    def _renumber_rows(self) -> None:
        for row in range(self.table.rowCount()):
            for column in range(self.table.columnCount()):
                widget = self.table.cellWidget(row, column)
                if widget is None:
                    continue
                widget.setProperty("price_row", row)
                if isinstance(widget, NoWheelSpinBox):
                    widget.lineEdit().setProperty("price_row", row)

    def save(self) -> None:
        rows = []
        for row in range(self.table.rowCount()):
            department = self.table.cellWidget(row, 0).text().strip()
            name_widget = self.table.cellWidget(row, 1)
            name = name_widget.text().strip()
            if not department or not name:
                QMessageBox.warning(self, "Не заполнено", f"Строка {row + 1}: укажи отдел и название работы.")
                return
            rows.append({
                "id": name_widget.property("work_type_id"),
                "department": department,
                "name": name,
                "price": self.table.cellWidget(row, 2).value(),
                "aliases": [x.strip() for x in self.table.cellWidget(row, 3).text().split(",")],
                "enabled": self.table.cellWidget(row, 4).isChecked(),
            })
        try:
            self.db.replace_work_types(rows)
        except Exception as exc:
            QMessageBox.critical(self, "Не удалось сохранить", str(exc))
            return
        self.refresh()
        self.data_changed.emit()
        notify(self, "Изменения сохранены", "Новые цены будут применяться к следующим импортированным отчётам.")


class ArchiveDetailsDialog(QDialog):
    def __init__(self, db: Database, week_id: int, title: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Отчёты: {title}")
        self.resize(1180, 680)
        root = QVBoxLayout(self)
        heading = QLabel(f"Отчёты за {title}")
        heading.setObjectName("pageTitle")
        root.addWidget(heading)
        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(["Static ID", "Сотрудник", "Статус", "Работа", "Принято", "Цена", "Сумма", "Доказательства", "Комментарий"])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.Fixed)
        self.table.setColumnWidth(7, 190)
        self.table.horizontalHeader().setSectionResizeMode(8, QHeaderView.Stretch)
        for col in (0, 1, 2, 4, 5, 6):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        rows = []
        for report in db.reports(week_id):
            full_report, items = db.report(int(report["id"]))
            for item in items:
                rows.append((full_report, item))
        self.table.setRowCount(len(rows))
        for row_index, (report, item) in enumerate(rows):
            amount = int(item["accepted_count"]) * int(item["price_snapshot"])
            values = [
                report["static_id"], report["employee_name"], STATUS_LABELS[report["status"]],
                item["work_name"] or item["raw_name"], item["accepted_count"], money(item["price_snapshot"]), money(amount), "", report["reviewer_comment"] or "—",
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(str(value))
                if column in (4, 5, 6):
                    cell.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row_index, column, cell)
            urls = extract_urls(item["evidence_url"])
            self.table.setCellWidget(row_index, 7, EvidenceLinks(urls))
            self.table.setRowHeight(row_index, max(48, 27 * max(1, len(urls)) + 10))
        root.addWidget(self.table, 1)
        close = QPushButton("Закрыть")
        close.clicked.connect(self.accept)
        root.addWidget(close, alignment=Qt.AlignRight)


class ArchivePage(QWidget):
    data_changed = Signal()

    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 22)
        root.setSpacing(16)
        header, actions = page_header(
            "Отчётные периоды",
            "Создавай новый период вручную, когда текущий завершён.",
        )
        self.create_button = QPushButton("+ Создать период")
        self.create_button.setObjectName("primary")
        self.create_button.clicked.connect(self.create_period)
        self.view_button = QPushButton("Просмотреть отчёты")
        self.view_button.clicked.connect(self.view_selected)
        self.export_button = QPushButton("Экспорт выбранного периода")
        self.export_button.clicked.connect(self.export_selected)
        actions.addWidget(self.create_button)
        actions.addWidget(self.view_button)
        actions.addWidget(self.export_button)
        root.addWidget(header)
        card = Card()
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Период", "Статус", "Отчётов", "Ожидают", "Сотрудников", "Начислено"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 6):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.doubleClicked.connect(self.view_selected)
        card.box.addWidget(self.table)
        root.addWidget(card, 1)
        self.refresh()

    def refresh(self) -> None:
        weeks = self.db.weeks()
        self.table.setRowCount(len(weeks))
        for index, week in enumerate(weeks):
            stats = self.db.week_stats(int(week["id"]))
            values = [week["title"], "Активный" if week["status"] == "current" else "Архив", stats["reports_count"], stats["pending_count"], stats["employees_count"], money(stats["raw_total"])]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, int(week["id"]))
                self.table.setItem(index, col, item)
        if weeks:
            self.table.selectRow(0)

    def create_period(self) -> None:
        dialog = CreateWeekDialog(self.db, self)
        if dialog.exec() != QDialog.Accepted:
            return
        start, end = dialog.dates()
        try:
            self.db.create_week(start, end)
        except ValueError as exc:
            QMessageBox.warning(self, "Не удалось создать период", str(exc))
            return
        self.refresh()
        self.data_changed.emit()
        notify(
            self,
            "Новый период создан",
            f"Активный период: {start.strftime('%d.%m.%Y')} — {end.strftime('%d.%m.%Y')}.\n"
            "Предыдущий период сохранён в архиве.",
        )

    def export_selected(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        week_id = int(self.table.item(row, 0).data(Qt.UserRole))
        if not self.db.aggregates(week_id):
            QMessageBox.warning(self, "Экспорт пуст", "В этой неделе нет одобренных отчётов.")
            return
        text = self.db.export_text(week_id)
        name = self.table.item(row, 0).text().replace(".", "-").replace(" — ", "_")
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить премии", str(exports_dir() / f"premium_{name}.txt"), "Текстовый файл (*.txt)")
        if path:
            Path(path).write_text(text + "\n", encoding="utf-8-sig")
            notify(self, "Экспорт готов", f"Файл сохранён:\n{path}")

    def view_selected(self, _index=None) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        week_id = int(self.table.item(row, 0).data(Qt.UserRole))
        ArchiveDetailsDialog(self.db, week_id, self.table.item(row, 0).text(), self).exec()


class SettingsPage(QWidget):
    data_changed = Signal()

    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 22)
        root.setSpacing(16)
        header, _ = page_header("Настройки", "Правила расчёта, экспорт и резервные копии.")
        root.addWidget(header)
        card = Card()
        form = QFormLayout()
        self.limit = NoWheelSpinBox()
        self.limit.setRange(0, 100_000_000)
        self.limit.setSingleStep(10_000)
        self.limit.setSuffix(" $")
        self.limit.setValue(int(db.setting("weekly_limit", "150000")))
        self.comment = QLineEdit(db.setting("export_comment", "Премия"))
        self.bulk_comment = QLineEdit(db.setting("bulk_export_comment", "Премия GOV"))
        form.addRow("Максимум на Static ID за неделю", self.limit)
        form.addRow("Комментарий отчётов в TXT", self.comment)
        form.addRow("Комментарий быстрого списка", self.bulk_comment)
        card.box.addLayout(form)
        save = QPushButton("Сохранить настройки")
        save.setObjectName("primary")
        save.clicked.connect(self.save)
        card.box.addWidget(save, alignment=Qt.AlignRight)
        root.addWidget(card)
        storage = Card()
        title = QLabel("Данные приложения")
        title.setObjectName("sectionTitle")
        storage.box.addWidget(title)
        path = QLabel(str(db.path.parent.parent))
        path.setObjectName("muted")
        path.setTextInteractionFlags(Qt.TextSelectableByMouse)
        storage.box.addWidget(path)
        buttons = QHBoxLayout()
        open_folder = QPushButton("Открыть папку данных")
        open_folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(db.path.parent.parent))))
        backup = QPushButton("Создать резервную копию")
        backup.clicked.connect(self.backup)
        buttons.addWidget(open_folder)
        buttons.addWidget(backup)
        buttons.addStretch(1)
        storage.box.addLayout(buttons)
        root.addWidget(storage)
        updates = Card()
        update_title = QLabel("Обновления")
        update_title.setObjectName("sectionTitle")
        self.update_status = QLabel(f"Установлена версия {CURRENT_VERSION}")
        self.update_status.setObjectName("muted")
        self.update_status.setWordWrap(True)
        repository = QLabel(f'<a href="{REPOSITORY_URL}">github.com/flaunti/BonusDesk ↗</a>')
        repository.setOpenExternalLinks(True)
        repository.setTextInteractionFlags(Qt.TextBrowserInteraction)
        author = QLabel("Автор: Edward Saint  ·  Static ID 46604")
        author.setObjectName("muted")
        self.auto_updates = QCheckBox("Проверять обновления автоматически")
        self.auto_updates.setChecked(db.setting("update_check_enabled", "1") == "1")
        check_button = QPushButton("Проверить обновления")
        check_button.clicked.connect(lambda: self.check_updates(silent=False))
        update_actions = QHBoxLayout()
        update_actions.addWidget(self.auto_updates)
        update_actions.addStretch(1)
        update_actions.addWidget(check_button)
        updates.box.addWidget(update_title)
        updates.box.addWidget(self.update_status)
        updates.box.addWidget(repository)
        updates.box.addWidget(author)
        updates.box.addLayout(update_actions)
        root.addWidget(updates)
        root.addStretch(1)

        self.update_checker = UpdateChecker(self)
        self.update_checker.finished.connect(self._update_finished)
        self.update_checker.failed.connect(self._update_failed)
        self._silent_update_check = False

    def save(self) -> None:
        comment = self.comment.text().replace(";", ",").strip() or "Премия"
        self.db.set_setting("weekly_limit", str(self.limit.value()))
        self.db.set_setting("export_comment", comment)
        bulk_comment = self.bulk_comment.text().replace(";", ",").strip() or "Премия GOV"
        self.db.set_setting("bulk_export_comment", bulk_comment)
        self.db.set_setting("update_check_enabled", "1" if self.auto_updates.isChecked() else "0")
        self.comment.setText(comment)
        self.bulk_comment.setText(bulk_comment)
        self.data_changed.emit()
        notify(self, "Настройки сохранены", "Лимит, комментарии экспорта и параметры обновлений сохранены.")

    def backup(self) -> None:
        path = self.db.backup(backups_dir())
        notify(self, "Резервная копия создана", f"Сохранено:\n{path}")

    def check_updates(self, silent: bool = False) -> None:
        self._silent_update_check = silent
        self.update_status.setObjectName("muted")
        self.update_status.setStyleSheet("")
        self.update_status.setText("Проверяю последнюю версию…")
        self.update_checker.check()

    def _update_finished(self, info: UpdateInfo) -> None:
        self.db.set_setting("last_update_check", date.today().isoformat())
        if info.is_newer:
            self.update_status.setObjectName("warning")
            self.update_status.setStyleSheet("")
            self.update_status.setText(f"Доступна версия {info.latest_version}. Установлена {info.current_version}.")
            answer = QMessageBox.question(
                self,
                "Доступно обновление",
                f"Вышла версия BonusDesk {info.latest_version}.\n\nОткрыть страницу загрузки?",
                QMessageBox.Open | QMessageBox.Cancel,
                QMessageBox.Open,
            )
            if answer == QMessageBox.Open:
                QDesktopServices.openUrl(QUrl(info.release_url))
        else:
            self.update_status.setObjectName("success")
            self.update_status.setStyleSheet("")
            self.update_status.setText(f"Установлена актуальная версия {info.current_version}.")
            if not self._silent_update_check:
                notify(self, "Обновлений нет", "Установлена актуальная версия BonusDesk.")

    def _update_failed(self, message: str) -> None:
        self.update_status.setObjectName("muted")
        self.update_status.setStyleSheet("")
        self.update_status.setText("Не удалось проверить обновления. Приложение продолжит работать офлайн.")
        if not self._silent_update_check:
            QMessageBox.warning(self, "Проверка обновлений", f"Не удалось получить данные о релизе.\n\n{message}")


class MainWindow(QMainWindow):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(str(resource_path("assets/bonusdesk.ico"))))
        self.resize(1380, 860)
        self.setMinimumSize(1120, 700)
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        nav = QVBoxLayout(sidebar)
        nav.setContentsMargins(16, 22, 16, 18)
        nav.setSpacing(6)
        brand_row = QHBoxLayout()
        logo = QLabel()
        logo.setToolTip("BonusDesk")
        pixmap = QPixmap(str(resource_path("assets/bonusdesk.png")))
        logo.setPixmap(pixmap.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        brand = QLabel("BonusDesk")
        brand.setObjectName("brand")
        accent = QLabel("BONUS REVIEW")
        accent.setObjectName("brandAccent")
        brand_text.addWidget(brand)
        brand_text.addWidget(accent)
        brand_row.addWidget(logo)
        brand_row.addLayout(brand_text)
        brand_row.addStretch(1)
        nav.addLayout(brand_row)
        nav.addSpacing(24)
        self.nav_buttons: list[QPushButton] = []
        entries = [
            ("Проверка отчётов", 0),
            ("Итоги недели", 1),
            ("Быстрый список", 2),
            ("Виды работ", 3),
            ("Архив", 4),
            ("Настройки", 5),
        ]
        for text, index in entries:
            button = QPushButton(text)
            button.setObjectName("nav")
            button.setCheckable(True)
            button.clicked.connect(lambda _=False, index=index: self.navigate(index))
            self.nav_buttons.append(button)
            nav.addWidget(button)
        nav.addStretch(1)
        version = QLabel(f"Версия {CURRENT_VERSION}")
        version.setObjectName("sidebarMeta")
        nav.addWidget(version)
        layout.addWidget(sidebar)

        self.stack = QStackedWidget()
        self.review_page = ReviewPage(db)
        self.summary_page = SummaryPage(db)
        self.bulk_page = BulkListPage(db)
        self.price_page = PricePage(db)
        self.archive_page = ArchivePage(db)
        self.settings_page = SettingsPage(db)
        for page in (self.review_page, self.summary_page, self.bulk_page, self.price_page, self.archive_page, self.settings_page):
            self.stack.addWidget(page)
        layout.addWidget(self.stack, 1)

        self.review_page.data_changed.connect(self.refresh_dependent)
        self.price_page.data_changed.connect(self.refresh_dependent)
        self.archive_page.data_changed.connect(self.refresh_dependent)
        self.settings_page.data_changed.connect(self.refresh_dependent)
        status = QStatusBar()
        status.showMessage("Готово к работе")
        self.setStatusBar(status)
        self.navigate(0)
        if db.setting("update_check_enabled", "1") == "1" and db.setting("last_update_check", "") != date.today().isoformat():
            QTimer.singleShot(1800, lambda: self.settings_page.check_updates(silent=True))

    def navigate(self, index: int) -> None:
        if self.stack.currentIndex() == 0 and index != 0:
            self.review_page.persist_if_dirty()
        self.stack.setCurrentIndex(index)
        for button_index, button in enumerate(self.nav_buttons):
            button.setChecked(button_index == index)
        if index == 0:
            self.review_page.refresh()
        elif index == 1:
            self.summary_page.refresh()
        elif index == 3:
            self.price_page.refresh()
        elif index == 4:
            self.archive_page.refresh()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API name
        self.review_page.persist_if_dirty()
        super().closeEvent(event)

    def refresh_dependent(self) -> None:
        self.summary_page.refresh()
        self.archive_page.refresh()
        self.bulk_page.comment.setText(self.db.setting("bulk_export_comment", "Премия GOV"))
        if self.review_page.current_report_id:
            self.review_page.load_report(self.review_page.current_report_id)
