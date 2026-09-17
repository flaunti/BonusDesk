from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .bulk_parser import BulkParseResult, parse_bulk_payments
from .database import Database
from .paths import exports_dir
from .widgets import Card, money, page_header


class BulkListPage(QWidget):
    def __init__(self, db: Database):
        super().__init__()
        self.db = db
        self.result = BulkParseResult()

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 22, 26, 22)
        root.setSpacing(16)
        header, actions = page_header(
            "Быстрый список",
            "Преобразование готового списка выплат в TXT без проверки отчётов.",
        )
        paste = QPushButton("Вставить из буфера")
        paste.clicked.connect(self.paste_clipboard)
        clear = QPushButton("Очистить")
        clear.clicked.connect(self.clear)
        actions.addWidget(clear)
        actions.addWidget(paste)
        root.addWidget(header)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        source_card = Card()
        source_title = QLabel("Исходный список")
        source_title.setObjectName("sectionTitle")
        source_hint = QLabel("Одна выплата на строку: Имя | Static ID | должность | сумма")
        source_hint.setObjectName("muted")
        source_hint.setWordWrap(True)
        self.source = QTextEdit()
        self.source.setPlaceholderText(
            "Alex Example | 100001 | 15 | 100.000$\n"
            "Edward Saint | 46604 | 14 | 100.000$\n\n"
            "Итоговая сумма: 200.000$"
        )
        self.source.textChanged.connect(self._mark_dirty)
        comment_row = QHBoxLayout()
        comment_label = QLabel("Комментарий в TXT")
        comment_label.setObjectName("muted")
        self.comment = QLineEdit(db.setting("bulk_export_comment", "Премия GOV"))
        self.comment.setMaximumWidth(240)
        comment_row.addWidget(comment_label)
        comment_row.addWidget(self.comment)
        comment_row.addStretch(1)
        parse_button = QPushButton("Разобрать список")
        parse_button.setObjectName("primary")
        parse_button.clicked.connect(self.parse)
        source_card.box.addWidget(source_title)
        source_card.box.addWidget(source_hint)
        source_card.box.addWidget(self.source, 1)
        source_card.box.addLayout(comment_row)
        source_card.box.addWidget(parse_button, alignment=Qt.AlignRight)
        source_card.setMinimumWidth(390)
        splitter.addWidget(source_card)

        preview_card = Card()
        preview_title = QLabel("Готовые выплаты")
        preview_title.setObjectName("sectionTitle")
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Сотрудник", "Static ID", "Должность", "Сумма"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.status = QLabel("Вставь список слева и нажми «Разобрать список».")
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        totals = QHBoxLayout()
        self.count_label = QLabel("0 сотрудников")
        self.count_label.setObjectName("muted")
        self.total_label = QLabel("0 $")
        self.total_label.setObjectName("money")
        totals.addWidget(self.count_label)
        totals.addStretch(1)
        totals.addWidget(self.total_label)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.copy_button = QPushButton("Скопировать TXT")
        self.copy_button.clicked.connect(self.copy_export)
        self.save_button = QPushButton("Сохранить TXT")
        self.save_button.setObjectName("primary")
        self.save_button.clicked.connect(self.save_export)
        buttons.addWidget(self.copy_button)
        buttons.addWidget(self.save_button)
        preview_card.box.addWidget(preview_title)
        preview_card.box.addWidget(self.table, 1)
        preview_card.box.addWidget(self.status)
        preview_card.box.addLayout(totals)
        preview_card.box.addLayout(buttons)
        splitter.addWidget(preview_card)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 6)
        splitter.setSizes([430, 650])
        root.addWidget(splitter, 1)
        self._set_export_enabled(False)

    def _set_export_enabled(self, enabled: bool) -> None:
        self.copy_button.setEnabled(enabled)
        self.save_button.setEnabled(enabled)

    def _mark_dirty(self) -> None:
        self._set_export_enabled(False)
        self.status.setObjectName("muted")
        self.status.setStyleSheet("")
        self.status.setText("Список изменён — обнови предпросмотр.")

    def paste_clipboard(self) -> None:
        self.source.setPlainText(QApplication.clipboard().text())
        self.parse()

    def clear(self) -> None:
        self.source.clear()
        self.result = BulkParseResult()
        self.table.setRowCount(0)
        self.count_label.setText("0 сотрудников")
        self.total_label.setText("0 $")
        self.status.setText("Вставь список слева и нажми «Разобрать список».")
        self._set_export_enabled(False)

    def parse(self) -> None:
        self.result = parse_bulk_payments(self.source.toPlainText())
        self.table.setRowCount(len(self.result.payments))
        for row, payment in enumerate(self.result.payments):
            values = [payment.employee_name, payment.static_id, payment.position, money(payment.amount)]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 3:
                    item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(row, column, item)

        count = len(self.result.payments)
        self.count_label.setText(f"Сотрудников: {count}")
        self.total_label.setText(money(self.result.total))
        messages: list[str] = []
        status_kind = "success"
        if not count:
            messages.append("Не найдено ни одной строки с выплатой.")
            status_kind = "warning"
        elif self.result.total_matches is True:
            messages.append("Итоговая сумма совпадает с указанной в списке.")
        elif self.result.total_matches is False:
            messages.append(
                f"Итог не совпадает: в списке {money(self.result.declared_total or 0)}, "
                f"по строкам {money(self.result.total)}."
            )
            status_kind = "warning"
        else:
            messages.append("Список готов. Итоговая сумма в исходном тексте не указана.")
        if self.result.duplicate_static_ids:
            messages.append("Повторяющиеся Static ID объединены: " + ", ".join(self.result.duplicate_static_ids) + ".")
            status_kind = "warning"
        if self.result.service_lines:
            messages.append(f"Служебных строк пропущено: {self.result.service_lines}.")
        if self.result.ignored_lines:
            messages.append(f"Нераспознанных строк: {len(self.result.ignored_lines)}.")
            status_kind = "warning"
        self.status.setObjectName(status_kind)
        self.status.setStyleSheet("")
        self.status.setText(" ".join(messages))
        self._set_export_enabled(bool(count))

    def export_text(self) -> str:
        return self.result.export_text(self.comment.text())

    def copy_export(self) -> None:
        if not self.result.payments:
            return
        QApplication.clipboard().setText(self.export_text())
        QMessageBox.information(self, "Скопировано", "Список выплат скопирован в буфер обмена.")

    def save_export(self) -> None:
        if not self.result.payments:
            return
        suggested = exports_dir() / f"premium_list_{date.today().isoformat()}.txt"
        path, _ = QFileDialog.getSaveFileName(self, "Сохранить список выплат", str(suggested), "Текстовый файл (*.txt)")
        if not path:
            return
        Path(path).write_text(self.export_text() + "\n", encoding="utf-8-sig")
        QMessageBox.information(self, "Экспорт готов", f"Файл сохранён:\n{path}")
