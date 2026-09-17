from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from bonusdesk.bulk_parser import parse_bulk_payments, parse_money
from bonusdesk.database import Database, DuplicateReportError
from bonusdesk.parser import ParsedItem, ParsedReport, parse_report
from bonusdesk.version import version_tuple


AD_REPORT = """
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
https://example.test/proof/ad
"""


ED_REPORT = """
Отчёт на премию
Имя фамилия
Second Employee
Ваш Static ID.
100002
Ваш основной отдел:
ED
Ваш дополнительный отдел:
Отсутствует.
Проведение мероприятия (кол-во):
23
Проведение мероприятия (док-ва):
https://example.test/proof/ed-one
Написание T3 (кол-во):
1
Написание T3 (док-ва):
https://example.test/proof/ed-two
"""


GOV_LIST = """
Employee One | 200001 | Director | Example Org
Employee One | 200001 | 15 | 100.000$
Employee Two | 200002 | 14 | 100.000$
Employee Three | 200003 | 14 | 100.000$
Employee Four | 200004 | 14 | 100.000$

Employee Five | 200005 | 13 | 100.000$
Employee Six | 200006 | 13 | 100.000$

Employee Seven | 200007 | 12 | 100.000$
Employee Eight | 200008 | 12 | 100.000$
Employee Nine | 200009 | 12 | 100.000$
Employee Ten | 200010 | 11 | 100.000$
Employee Eleven | 200011 | 10 | 100.000$
Employee Twelve | 200012 | 4 | 100.000$
Employee Thirteen | 200013 | 10 | 100.000$
Employee Fourteen | 200014 | 9 | 100.000$
Employee Fifteen | 200015 | 9 | 100.000$
Employee Sixteen | 200016 | 10 | 100.000$
Employee Seventeen | 200017 | 11 | 100.000$
Employee Eighteen | 200018 | 11 | 100.000$
Employee Nineteen | 200019 | 6 | 100.000$
Employee Twenty | 200020 | 3 | 100.000$

Итоговая сумма: 2.000.000$
"""


class BulkPaymentTests(unittest.TestCase):
    def test_gov_list_is_converted_to_twenty_payments(self):
        result = parse_bulk_payments(GOV_LIST)
        self.assertEqual(len(result.payments), 20)
        self.assertEqual(result.total, 2_000_000)
        self.assertTrue(result.total_matches)
        self.assertEqual(result.service_lines, 1)
        self.assertEqual(result.payments[0].static_id, "200001")
        self.assertEqual(result.payments[0].amount, 100_000)
        self.assertEqual(
            result.export_text("Премия GOV").splitlines()[:3],
            [
                "staticId;amount;comment",
                "200001;100000;Премия GOV",
                "200002;100000;Премия GOV",
            ],
        )

    def test_duplicate_static_ids_are_combined(self):
        result = parse_bulk_payments("A | 1 | 10 | 50.000$\nA | 1 | 10 | 25.000$")
        self.assertEqual(len(result.payments), 1)
        self.assertEqual(result.payments[0].amount, 75_000)
        self.assertEqual(result.duplicate_static_ids, ["1"])

    def test_money_and_versions_are_parsed(self):
        self.assertEqual(parse_money("2.000.000$"), 2_000_000)
        self.assertGreater(version_tuple("v2.1.0"), version_tuple("2.0.9"))


class ParserTests(unittest.TestCase):
    def test_parses_clipboard_report(self):
        report = parse_report(AD_REPORT)
        self.assertEqual(report.employee_name, "Test Employee")
        self.assertEqual(report.static_id, "100001")
        self.assertEqual(report.primary_department, "AD")
        self.assertEqual(len(report.items), 1)
        self.assertEqual(report.items[0].claimed_count, 21)
        self.assertIn("example.test", report.items[0].evidence_url)

    def test_parses_multiple_ed_items(self):
        report = parse_report(ED_REPORT)
        self.assertEqual([item.name for item in report.items], ["Проведение мероприятия", "Написание T3"])
        self.assertEqual([item.claimed_count for item in report.items], [23, 1])

    def test_form_label_with_nested_parentheses_and_period(self):
        text = """Имя фамилия\nTest Person\nВаш Static ID.\n123\nОператор (съёмка видео)(кол-во).\n2\nОператор (съёмка видео)(док-ва):\nhttps://example.com/proof"""
        report = parse_report(text)
        self.assertEqual(report.items[0].name, "Оператор (съёмка видео)")
        self.assertEqual(report.items[0].claimed_count, 2)

    def test_multiple_evidence_links_are_preserved(self):
        text = """Имя фамилия\nTest Person\nВаш Static ID.\n123\nМонтаж (кол-во):\n1\nМонтаж (док-ва):\nhttps://example.com/one\nhttps://example.com/two"""
        report = parse_report(text)
        self.assertEqual(report.items[0].evidence_url.splitlines(), ["https://example.com/one", "https://example.com/two"])


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "bonusdesk.db")
        self.week_id = int(self.db.current_week()["id"])

    def tearDown(self):
        self.tmp.cleanup()

    def test_seed_prices_match_current_price_list(self):
        prices = {(row["department"], row["name"]): row["price"] for row in self.db.work_types()}
        self.assertEqual(prices[("AD", "Подача 1 зеленого эфира")], 5000)
        self.assertEqual(prices[("ED", "Проведение мероприятия")], 10000)
        self.assertEqual(prices[("ED", "Написание T3")], 5000)
        self.assertEqual(prices[("HA", "Проверка отчета на повышение")], 3000)
        self.assertEqual(prices[("ND", "Монтаж")], 40000)

    def test_all_current_form_labels_match_price_rows(self):
        labels = [
            "Принятие человека во фракцию", "Проведение экзамена", "Проверка отчета на повышение",
            "1 час дежурства в холле", "Зелёный эфир/смс о наборе", "Подача 1 смс",
            "Подача 1 зеленого эфира", "Проведение мероприятия", "Проведение ГМП", "Написание T3",
            "Оператор (съёмка видео)", "Корреспондент (озвучка/ведущий в видео)", "Монтаж",
            "Написание сценария", "Написание журнала", "Написание статьи", "Редактура материала",
            "Составление гороскопа", "1 отчет об услугах и казне фракции, складе, онлайне",
            "Проверенные отчеты на повышение", "Проверенные запросы на повышение",
        ]
        for label in labels:
            with self.subTest(label=label):
                self.assertIsNotNone(self.db.match_work_type(label, ()))

    def test_custom_price_survives_restart(self):
        with self.db.connect() as con:
            con.execute("UPDATE work_types SET price=7777 WHERE department='AD' AND name='Подача 1 смс'")
        Database(self.db.path)
        row = self.db.match_work_type("Подача 1 смс", ("AD",))
        self.assertEqual(row["price"], 7777)

    def test_v1_names_migrate_to_current_form_without_price_loss(self):
        with self.db.connect() as con:
            con.execute(
                "UPDATE work_types SET name='Проведение МП', price=12345 "
                "WHERE department='ED' AND name='Проведение мероприятия'"
            )
            con.execute("UPDATE settings SET value='1' WHERE key='price_seed_version'")
        Database(self.db.path)
        row = self.db.match_work_type("Проведение мероприятия", ("ED",))
        self.assertEqual(row["name"], "Проведение мероприятия")
        self.assertEqual(row["price"], 12345)

    def test_legacy_general_department_is_renamed_without_data_loss(self):
        legacy_department = "".join(("F", "R"))
        with self.db.connect() as con:
            con.execute("UPDATE work_types SET department=? WHERE department='Общее'", (legacy_department,))
            con.execute("UPDATE settings SET value='2' WHERE key='price_seed_version'")
        Database(self.db.path)
        departments = {row["department"] for row in self.db.work_types()}
        self.assertIn("Общее", departments)
        self.assertNotIn(legacy_department, departments)

    def test_import_match_calculate_and_limit(self):
        report_id = self.db.add_report(self.week_id, parse_report(ED_REPORT))
        report, items = self.db.report(report_id)
        self.assertEqual([row["price_snapshot"] for row in items], [10000, 5000])
        self.db.set_report_status(report_id, "approved")
        rows = self.db.aggregates(self.week_id)
        self.assertEqual(rows[0]["raw_amount"], 235000)
        self.assertEqual(rows[0]["payout"], 150000)
        self.assertEqual(
            self.db.export_text(self.week_id),
            "staticId;amount;comment\n100002;150000;Премия",
        )

    def test_empty_export_still_has_required_header(self):
        self.assertEqual(self.db.export_text(self.week_id), "staticId;amount;comment")

    def test_multiple_reports_are_combined_before_limit(self):
        first = ParsedReport("A", "300001", "ND", "", [ParsedItem("Монтаж", 2, "https://a.test/1")], "first")
        second = ParsedReport("A", "300001", "ND", "", [ParsedItem("Написание статьи", 4, "https://a.test/2")], "second")
        first_id = self.db.add_report(self.week_id, first)
        second_id = self.db.add_report(self.week_id, second)
        self.db.set_report_status(first_id, "approved")
        self.db.set_report_status(second_id, "approved")
        row = self.db.aggregates(self.week_id)[0]
        self.assertEqual(row["raw_amount"], 160000)
        self.assertEqual(row["payout"], 150000)
        self.assertEqual(row["reports_count"], 2)

    def test_duplicate_report_is_rejected(self):
        parsed = parse_report(AD_REPORT)
        self.db.add_report(self.week_id, parsed)
        with self.assertRaises(DuplicateReportError):
            self.db.add_report(self.week_id, parsed)

    def test_duplicate_evidence_is_flagged(self):
        one = ParsedReport("A", "1", "AD", "", [ParsedItem("Подача 1 смс", 1, "https://proof.test/x")], "one")
        two = ParsedReport("B", "2", "AD", "", [ParsedItem("Подача 1 смс", 1, "https://proof.test/x/")], "two")
        self.db.add_report(self.week_id, one)
        two_id = self.db.add_report(self.week_id, two)
        self.assertEqual(len(self.db.duplicate_evidence(two_id)), 1)

    def test_each_link_in_multi_link_field_is_checked_for_duplicates(self):
        one = ParsedReport("A", "1", "AD", "", [ParsedItem("Подача 1 смс", 1, "https://proof.test/one\nhttps://proof.test/two")], "one")
        two = ParsedReport("B", "2", "AD", "", [ParsedItem("Подача 1 смс", 1, "https://proof.test/two")], "two")
        self.db.add_report(self.week_id, one)
        two_id = self.db.add_report(self.week_id, two)
        self.assertEqual(len(self.db.duplicate_evidence(two_id)), 1)


if __name__ == "__main__":
    unittest.main()
