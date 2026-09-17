from __future__ import annotations

import json
import shutil
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterator

from .parser import ParsedReport, extract_urls, normalize_url, normalize_work_name


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS weeks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date_start TEXT NOT NULL UNIQUE,
    date_end TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'current',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS work_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    department TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL,
    price INTEGER NOT NULL DEFAULT 0 CHECK(price >= 0),
    aliases TEXT NOT NULL DEFAULT '[]',
    enabled INTEGER NOT NULL DEFAULT 1,
    UNIQUE(department, name)
);
CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    week_id INTEGER NOT NULL REFERENCES weeks(id) ON DELETE CASCADE,
    employee_name TEXT NOT NULL,
    static_id TEXT NOT NULL,
    primary_department TEXT NOT NULL DEFAULT '',
    secondary_department TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',
    reviewer_comment TEXT NOT NULL DEFAULT '',
    source_text TEXT NOT NULL DEFAULT '',
    source_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    reviewed_at TEXT,
    UNIQUE(week_id, source_hash)
);
CREATE TABLE IF NOT EXISTS report_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    work_type_id INTEGER REFERENCES work_types(id) ON DELETE SET NULL,
    raw_name TEXT NOT NULL,
    claimed_count INTEGER NOT NULL DEFAULT 0 CHECK(claimed_count >= 0),
    accepted_count INTEGER NOT NULL DEFAULT 0 CHECK(accepted_count >= 0),
    evidence_url TEXT NOT NULL DEFAULT '',
    normalized_url TEXT NOT NULL DEFAULT '',
    price_snapshot INTEGER NOT NULL DEFAULT 0 CHECK(price_snapshot >= 0)
);
CREATE TABLE IF NOT EXISTS evidence_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_item_id INTEGER NOT NULL REFERENCES report_items(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    normalized_url TEXT NOT NULL,
    UNIQUE(report_item_id, normalized_url)
);
CREATE INDEX IF NOT EXISTS idx_reports_week_status ON reports(week_id, status);
CREATE INDEX IF NOT EXISTS idx_reports_static ON reports(static_id);
CREATE INDEX IF NOT EXISTS idx_items_url ON report_items(normalized_url);
CREATE INDEX IF NOT EXISTS idx_evidence_url ON evidence_links(normalized_url);
"""


class DuplicateReportError(ValueError):
    pass


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        con = sqlite3.connect(self.path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys = ON")
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def _initialize(self) -> None:
        with self.connect() as con:
            con.executescript(SCHEMA)
            defaults = {
                "weekly_limit": "150000",
                "export_comment": "Премия",
                "bulk_export_comment": "Премия GOV",
                "update_check_enabled": "1",
                "last_update_check": "",
                "theme": "light",
            }
            for key, value in defaults.items():
                con.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (key, value))
            seeded = con.execute("SELECT value FROM settings WHERE key='price_seed_version'").fetchone()
            seed_version = int(seeded["value"]) if seeded else 0
            if seed_version < 1:
                seed = [
                    ("ND", "Оператор (съёмка видео)", 40000, ["Оператор", "Съемка видео", "Оператор съёмка видео"]),
                    ("ND", "Корреспондент (озвучка/ведущий в видео)", 40000, ["Корреспондент", "Озвучка", "Ведущий в видео"]),
                    ("ND", "Монтаж", 40000, ["Монтаж видео"]),
                    ("ND", "Написание сценария", 15000, ["Сценарий"]),
                    ("ND", "Написание журнала", 40000, ["Журнал"]),
                    ("ND", "Написание статьи", 20000, ["Статья"]),
                    ("ND", "Редактура материала", 10000, ["Редактура", "Редактирование материала"]),
                    ("ND", "Составление гороскопа", 2500, ["Гороскоп"]),
                    ("AD", "Подача 1 смс", 2500, ["Подача СМС", "СМС"]),
                    ("AD", "Подача 1 зеленого эфира", 5000, ["Подача зеленого эфира", "Зеленый эфир", "Зелёный эфир"]),
                    ("HA", "Принятие человека во фракцию", 5000, ["Принятие человека", "Приём человека", "Принятие сотрудника"]),
                    ("HA", "Проведение экзамена", 5000, ["Экзамен"]),
                    ("HA", "1 час дежурства в холле", 5000, ["Час дежурства в холле", "Дежурство в холле"]),
                    ("HA", "Проверка отчета на повышение", 3000, ["Проверка отчёта на повышение", "Проверка отчета"]),
                    ("HA", "Зелёный эфир/смс о наборе", 3000, ["Зеленый эфир/смс о наборе", "Эфир о наборе", "СМС о наборе"]),
                    ("ED", "Проведение мероприятия", 10000, ["Проведение МП", "МП"]),
                    ("ED", "Проведение ГМП", 50000, ["Проведение глобального мероприятия", "ГМП"]),
                    ("ED", "Написание T3", 5000, ["Написание ТЗ", "Написание Т3", "ТЗ", "T3"]),
                    ("Общее", "1 отчет об услугах и казне фракции, складе, онлайне", 2000, ["Отчёт об услугах, казне, складе и онлайне", "1 отчёт об услугах и казне фракции, складе, онлайне"]),
                    ("Общее", "Проверенные отчёты на повышение", 0, ["Проверенные отчеты на повышение"]),
                    ("Общее", "Проверенные запросы на повышение", 0, ["Проверенные запросы на повышение"]),
                ]
                for department, name, price, aliases in seed:
                    con.execute(
                        "INSERT OR IGNORE INTO work_types(department,name,price,aliases) VALUES (?,?,?,?)",
                        (department, name, price, json.dumps(aliases, ensure_ascii=False)),
                    )
                con.execute("INSERT INTO settings(key,value) VALUES ('price_seed_version','1')")
                seed_version = 1
            if seed_version < 2:
                legacy_department = "".join(("F", "R"))
                con.execute("UPDATE work_types SET department='Общее' WHERE department=?", (legacy_department,))
                canonical_names = [
                    ("HA", "Принятие человека", "Принятие человека во фракцию"),
                    ("ED", "Проведение МП", "Проведение мероприятия"),
                    ("ED", "Написание ТЗ", "Написание T3"),
                    ("Общее", "Отчёт об услугах, казне, складе и онлайне", "1 отчет об услугах и казне фракции, складе, онлайне"),
                ]
                for department, old_name, new_name in canonical_names:
                    con.execute(
                        """UPDATE work_types SET name=?
                           WHERE department=? AND name=?
                             AND NOT EXISTS (
                                 SELECT 1 FROM work_types AS duplicate
                                 WHERE duplicate.department=? AND duplicate.name=?
                             )""",
                        (new_name, department, old_name, department, new_name),
                    )
                con.execute(
                    "INSERT INTO settings(key,value) VALUES ('price_seed_version','2') "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value"
                )
                seed_version = 2
            if seed_version < 3:
                legacy_department = "".join(("F", "R"))
                con.execute("UPDATE work_types SET department='Общее' WHERE department=?", (legacy_department,))
                con.execute(
                    "INSERT INTO settings(key,value) VALUES ('price_seed_version','3') "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value"
                )
            legacy_items = con.execute("SELECT id,evidence_url FROM report_items WHERE evidence_url<>''").fetchall()
            for legacy_item in legacy_items:
                for url in extract_urls(legacy_item["evidence_url"]):
                    con.execute(
                        "INSERT OR IGNORE INTO evidence_links(report_item_id,url,normalized_url) VALUES (?,?,?)",
                        (legacy_item["id"], url, normalize_url(url)),
                    )
        self.ensure_current_week()

    def setting(self, key: str, default: str = "") -> str:
        with self.connect() as con:
            row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self.connect() as con:
            con.execute(
                "INSERT INTO settings(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def ensure_current_week(self, today: date | None = None) -> int:
        today = today or date.today()
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        title = f"{start.strftime('%d.%m.%Y')} — {end.strftime('%d.%m.%Y')}"
        with self.connect() as con:
            con.execute("UPDATE weeks SET status='archived' WHERE status='current' AND date_start<>?", (start.isoformat(),))
            con.execute(
                "INSERT OR IGNORE INTO weeks(date_start,date_end,title,status) VALUES (?,?,?,'current')",
                (start.isoformat(), end.isoformat(), title),
            )
            con.execute("UPDATE weeks SET status='current' WHERE date_start=?", (start.isoformat(),))
            return int(con.execute("SELECT id FROM weeks WHERE date_start=?", (start.isoformat(),)).fetchone()["id"])

    def current_week(self) -> sqlite3.Row:
        week_id = self.ensure_current_week()
        with self.connect() as con:
            return con.execute("SELECT * FROM weeks WHERE id=?", (week_id,)).fetchone()

    def weeks(self) -> list[sqlite3.Row]:
        with self.connect() as con:
            return con.execute("SELECT * FROM weeks ORDER BY date_start DESC").fetchall()

    def work_types(self, enabled_only: bool = False) -> list[sqlite3.Row]:
        sql = "SELECT * FROM work_types"
        if enabled_only:
            sql += " WHERE enabled=1"
        sql += " ORDER BY department, name"
        with self.connect() as con:
            return con.execute(sql).fetchall()

    def replace_work_types(self, rows: list[dict]) -> None:
        with self.connect() as con:
            seen_ids: list[int] = []
            for row in rows:
                aliases = [x.strip() for x in row.get("aliases", []) if x.strip()]
                if row.get("id"):
                    con.execute(
                        "UPDATE work_types SET department=?,name=?,price=?,aliases=?,enabled=? WHERE id=?",
                        (row["department"].strip(), row["name"].strip(), int(row["price"]), json.dumps(aliases, ensure_ascii=False), int(row["enabled"]), int(row["id"])),
                    )
                    seen_ids.append(int(row["id"]))
                else:
                    cur = con.execute(
                        "INSERT INTO work_types(department,name,price,aliases,enabled) VALUES (?,?,?,?,?)",
                        (row["department"].strip(), row["name"].strip(), int(row["price"]), json.dumps(aliases, ensure_ascii=False), int(row["enabled"])),
                    )
                    seen_ids.append(int(cur.lastrowid))
            if seen_ids:
                placeholders = ",".join("?" for _ in seen_ids)
                con.execute(f"DELETE FROM work_types WHERE id NOT IN ({placeholders})", seen_ids)
            else:
                con.execute("DELETE FROM work_types")

    def match_work_type(self, name: str, departments: tuple[str, ...]) -> sqlite3.Row | None:
        needle = normalize_work_name(name)
        candidates = self.work_types(enabled_only=True)
        best = None
        for row in candidates:
            aliases = json.loads(row["aliases"] or "[]")
            names = [row["name"], *aliases]
            if any(normalize_work_name(item) == needle for item in names):
                if row["department"].casefold() in {department.casefold() for department in departments}:
                    return row
                best = best or row
        return best

    def add_report(self, week_id: int, report: ParsedReport) -> int:
        departments = tuple(x for x in (report.primary_department, report.secondary_department) if x and "отсутств" not in x.casefold())
        try:
            with self.connect() as con:
                cur = con.execute(
                    """INSERT INTO reports(week_id,employee_name,static_id,primary_department,secondary_department,source_text,source_hash)
                       VALUES (?,?,?,?,?,?,?)""",
                    (week_id, report.employee_name, report.static_id, report.primary_department, report.secondary_department, report.source_text, report.fingerprint),
                )
                report_id = int(cur.lastrowid)
                for item in report.items:
                    match = self.match_work_type(item.name, departments)
                    item_cursor = con.execute(
                        """INSERT INTO report_items(report_id,work_type_id,raw_name,claimed_count,accepted_count,evidence_url,normalized_url,price_snapshot)
                           VALUES (?,?,?,?,?,?,?,?)""",
                        (report_id, match["id"] if match else None, item.name, item.claimed_count, item.claimed_count, item.evidence_url, "", match["price"] if match else 0),
                    )
                    item_id = int(item_cursor.lastrowid)
                    for url in extract_urls(item.evidence_url):
                        con.execute(
                            "INSERT INTO evidence_links(report_item_id,url,normalized_url) VALUES (?,?,?)",
                            (item_id, url, normalize_url(url)),
                        )
                return report_id
        except sqlite3.IntegrityError as exc:
            if "reports.week_id, reports.source_hash" in str(exc) or "UNIQUE constraint failed" in str(exc):
                raise DuplicateReportError("Этот отчёт уже импортирован в текущую неделю.") from exc
            raise

    def reports(self, week_id: int, status: str | None = None) -> list[sqlite3.Row]:
        sql = """SELECT r.*, COALESCE(SUM(i.accepted_count*i.price_snapshot),0) raw_amount
                 FROM reports r LEFT JOIN report_items i ON i.report_id=r.id WHERE r.week_id=?"""
        params: list[object] = [week_id]
        if status:
            sql += " AND r.status=?"
            params.append(status)
        sql += " GROUP BY r.id ORDER BY CASE r.status WHEN 'pending' THEN 0 WHEN 'approved' THEN 1 ELSE 2 END, r.created_at DESC"
        with self.connect() as con:
            return con.execute(sql, params).fetchall()

    def report(self, report_id: int) -> tuple[sqlite3.Row, list[sqlite3.Row]]:
        with self.connect() as con:
            report = con.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
            items = con.execute(
                """SELECT i.*, w.name work_name, w.department work_department
                   FROM report_items i LEFT JOIN work_types w ON w.id=i.work_type_id
                   WHERE i.report_id=? ORDER BY i.id""",
                (report_id,),
            ).fetchall()
            return report, items

    def update_report(self, report_id: int, items: list[dict], comment: str = "") -> None:
        with self.connect() as con:
            con.execute("UPDATE reports SET reviewer_comment=? WHERE id=?", (comment.strip(), report_id))
            for item in items:
                work_type = con.execute("SELECT * FROM work_types WHERE id=?", (item.get("work_type_id"),)).fetchone() if item.get("work_type_id") else None
                price = int(item["price"] if item.get("price") is not None else (work_type["price"] if work_type else 0))
                con.execute(
                    "UPDATE report_items SET work_type_id=?,accepted_count=?,price_snapshot=? WHERE id=? AND report_id=?",
                    (item.get("work_type_id"), int(item["accepted_count"]), price, int(item["id"]), report_id),
                )

    def set_report_status(self, report_id: int, status: str, comment: str = "") -> None:
        if status not in {"pending", "approved", "rejected"}:
            raise ValueError("Unknown report status")
        reviewed_at = datetime.now().isoformat(timespec="seconds") if status != "pending" else None
        with self.connect() as con:
            con.execute(
                "UPDATE reports SET status=?,reviewer_comment=?,reviewed_at=? WHERE id=?",
                (status, comment.strip(), reviewed_at, report_id),
            )

    def delete_report(self, report_id: int) -> None:
        with self.connect() as con:
            con.execute("DELETE FROM reports WHERE id=?", (report_id,))

    def duplicate_evidence(self, report_id: int) -> list[sqlite3.Row]:
        with self.connect() as con:
            return con.execute(
                """SELECT current.report_item_id item_id, other_item.report_id, r.static_id,
                          r.employee_name, current.url evidence_url
                   FROM evidence_links current
                   JOIN evidence_links other
                     ON other.normalized_url=current.normalized_url AND other.id<>current.id
                   JOIN report_items current_item ON current_item.id=current.report_item_id
                   JOIN report_items other_item ON other_item.id=other.report_item_id
                   JOIN reports r ON r.id=other_item.report_id
                   WHERE current_item.report_id=?""",
                (report_id,),
            ).fetchall()

    def aggregates(self, week_id: int) -> list[sqlite3.Row]:
        limit = int(self.setting("weekly_limit", "150000"))
        with self.connect() as con:
            return con.execute(
                """SELECT r.static_id, MAX(r.employee_name) employee_name,
                          SUM(i.accepted_count*i.price_snapshot) raw_amount,
                          MIN(SUM(i.accepted_count*i.price_snapshot), ?) payout,
                          COUNT(DISTINCT r.id) reports_count
                   FROM reports r JOIN report_items i ON i.report_id=r.id
                   WHERE r.week_id=? AND r.status='approved'
                   GROUP BY r.static_id ORDER BY payout DESC, r.static_id""",
                (limit, week_id),
            ).fetchall()

    def export_text(self, week_id: int) -> str:
        comment = self.setting("export_comment", "Премия").replace(";", ",").replace("\n", " ").strip() or "Премия"
        lines = ["staticId;amount;comment"]
        lines.extend(f"{row['static_id']};{row['payout']};{comment}" for row in self.aggregates(week_id))
        return "\n".join(lines)

    def week_stats(self, week_id: int) -> sqlite3.Row:
        with self.connect() as con:
            return con.execute(
                """SELECT COUNT(DISTINCT r.id) reports_count,
                          COUNT(DISTINCT CASE WHEN r.status='pending' THEN r.id END) pending_count,
                          COUNT(DISTINCT CASE WHEN r.status='approved' THEN r.static_id END) employees_count,
                          COALESCE(SUM(CASE WHEN r.status='approved' THEN i.accepted_count*i.price_snapshot ELSE 0 END),0) raw_total
                   FROM reports r LEFT JOIN report_items i ON i.report_id=r.id WHERE r.week_id=?""",
                (week_id,),
            ).fetchone()

    def backup(self, backup_dir: Path, keep: int = 30) -> Path | None:
        if not self.path.exists():
            return None
        backup_dir.mkdir(parents=True, exist_ok=True)
        destination = backup_dir / f"bonusdesk_{datetime.now():%Y-%m-%d_%H-%M-%S}.db"
        shutil.copy2(self.path, destination)
        for old in sorted(backup_dir.glob("bonusdesk_*.db"), reverse=True)[keep:]:
            old.unlink(missing_ok=True)
        return destination
