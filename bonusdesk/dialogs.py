from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from .parser import ParsedItem, ParsedReport, ReportParseError, parse_report
from .widgets import NoWheelSpinBox


class ImportReportDialog(QDialog):
    def __init__(self, clipboard_text: str = "", manual: bool = False, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить отчёт вручную" if manual else "Импорт отчёта")
        self.resize(920, 720)
        self._parsed_source = ""

        root = QVBoxLayout(self)
        title = QLabel("Вставь текст отчёта целиком" if not manual else "Заполни данные отчёта")
        title.setObjectName("sectionTitle")
        root.addWidget(title)

        self.raw = QTextEdit()
        self.raw.setPlaceholderText("Имя фамилия\n...\nВаш Static ID.\n...\nНазвание работы (кол-во):\n...\nНазвание работы (док-ва):\n...")
        self.raw.setMaximumHeight(190)
        self.raw.setPlainText("" if manual else clipboard_text)
        root.addWidget(self.raw)

        actions = QHBoxLayout()
        parse_button = QPushButton("Разобрать текст")
        parse_button.setObjectName("primary")
        parse_button.clicked.connect(self.parse)
        add_row = QPushButton("+ Добавить работу")
        add_row.clicked.connect(self.add_empty_row)
        actions.addWidget(parse_button)
        actions.addWidget(add_row)
        actions.addStretch(1)
        root.addLayout(actions)

        form = QFormLayout()
        form.setHorizontalSpacing(18)
        self.employee = QLineEdit()
        self.static_id = QLineEdit()
        self.primary_department = QLineEdit()
        self.secondary_department = QLineEdit()
        form.addRow("Имя и фамилия", self.employee)
        form.addRow("Static ID", self.static_id)
        form.addRow("Основной отдел", self.primary_department)
        form.addRow("Дополнительный отдел", self.secondary_department)
        root.addLayout(form)

        self.items = QTableWidget(0, 4)
        self.items.setHorizontalHeaderLabels(["Вид работы", "Заявлено", "Доказательства", ""])
        self.items.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.items.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.items.setColumnWidth(1, 100)
        self.items.setColumnWidth(3, 60)
        self.items.verticalHeader().setVisible(False)
        self.items.verticalHeader().setDefaultSectionSize(46)
        root.addWidget(self.items, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        buttons.button(QDialogButtonBox.Ok).setText("Импортировать")
        buttons.button(QDialogButtonBox.Cancel).setText("Отмена")
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        if clipboard_text.strip() and not manual:
            self.parse(silent=True)

    def parse(self, _checked=False, silent: bool = False) -> None:
        try:
            parsed = parse_report(self.raw.toPlainText())
        except ReportParseError as exc:
            if not silent:
                QMessageBox.warning(self, "Не удалось разобрать отчёт", str(exc))
            return
        self._parsed_source = parsed.source_text
        self.employee.setText(parsed.employee_name)
        self.static_id.setText(parsed.static_id)
        self.primary_department.setText(parsed.primary_department)
        self.secondary_department.setText(parsed.secondary_department)
        self.items.setRowCount(0)
        for item in parsed.items:
            self.add_item(item)

    def add_empty_row(self) -> None:
        self.add_item(ParsedItem("", 1, ""))

    def add_item(self, item: ParsedItem) -> None:
        row = self.items.rowCount()
        self.items.insertRow(row)
        self.items.setItem(row, 0, QTableWidgetItem(item.name))
        count = NoWheelSpinBox()
        count.setRange(0, 100000)
        count.setValue(item.claimed_count)
        self.items.setCellWidget(row, 1, count)
        self.items.setItem(row, 2, QTableWidgetItem(item.evidence_url))
        remove = QPushButton("×")
        remove.setObjectName("danger")
        remove.setToolTip("Удалить строку")
        remove.clicked.connect(lambda _=False, button=remove: self._remove_button_row(button))
        self.items.setCellWidget(row, 3, remove)

    def _remove_button_row(self, button: QPushButton) -> None:
        for row in range(self.items.rowCount()):
            if self.items.cellWidget(row, 3) is button:
                self.items.removeRow(row)
                return

    def _validate_and_accept(self) -> None:
        if not self.employee.text().strip():
            QMessageBox.warning(self, "Не заполнено", "Укажи имя и фамилию сотрудника.")
            return
        if not self.static_id.text().strip().isdigit():
            QMessageBox.warning(self, "Не заполнено", "Static ID должен состоять только из цифр.")
            return
        if not self.result_report().items:
            QMessageBox.warning(self, "Не заполнено", "Добавь хотя бы один вид работы.")
            return
        self.accept()

    def result_report(self) -> ParsedReport:
        rows: list[ParsedItem] = []
        for row in range(self.items.rowCount()):
            name_item = self.items.item(row, 0)
            evidence_item = self.items.item(row, 2)
            name = name_item.text().strip() if name_item else ""
            if not name:
                continue
            count = self.items.cellWidget(row, 1)
            rows.append(ParsedItem(name, count.value(), evidence_item.text().strip() if evidence_item else ""))
        source = self._parsed_source or self.raw.toPlainText().strip()
        if not source:
            source = "|".join(
                [self.employee.text().strip(), self.static_id.text().strip(), *[f"{x.name}:{x.claimed_count}:{x.evidence_url}" for x in rows]]
            )
        return ParsedReport(
            employee_name=self.employee.text().strip(),
            static_id=self.static_id.text().strip(),
            primary_department=self.primary_department.text().strip(),
            secondary_department=self.secondary_department.text().strip(),
            items=rows,
            source_text=source,
        )
