from __future__ import annotations

import re
from dataclasses import dataclass, field


STATIC_ID_RE = re.compile(r"#?(\d{1,12})")
TOTAL_RE = re.compile(r"^итоговая\s+сумма\s*:", re.IGNORECASE)


def parse_money(value: str) -> int | None:
    """Parse integer amounts written as 100000, 100 000 or 100.000$."""
    digits = re.sub(r"\D", "", value or "")
    return int(digits) if digits else None


@dataclass(slots=True)
class BulkPayment:
    employee_name: str
    static_id: str
    position: str
    amount: int


@dataclass(slots=True)
class BulkParseResult:
    payments: list[BulkPayment] = field(default_factory=list)
    declared_total: int | None = None
    service_lines: int = 0
    ignored_lines: list[str] = field(default_factory=list)
    duplicate_static_ids: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(payment.amount for payment in self.payments)

    @property
    def total_matches(self) -> bool | None:
        if self.declared_total is None:
            return None
        return self.declared_total == self.total

    def export_text(self, comment: str = "Премия") -> str:
        safe_comment = comment.replace(";", ",").replace("\n", " ").strip() or "Премия"
        lines = ["staticId;amount;comment"]
        lines.extend(f"{payment.static_id};{payment.amount};{safe_comment}" for payment in self.payments)
        return "\n".join(lines)


def parse_bulk_payments(text: str) -> BulkParseResult:
    result = BulkParseResult()
    ordered: list[BulkPayment] = []
    by_static: dict[str, BulkPayment] = {}

    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if TOTAL_RE.match(line):
            result.declared_total = parse_money(line.split(":", 1)[-1])
            continue

        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 4:
            result.ignored_lines.append(line)
            continue

        static_match = STATIC_ID_RE.fullmatch(parts[1])
        amount = parse_money(parts[-1]) if any(symbol in parts[-1] for symbol in ("$", ".", ",", " ")) or parts[-1].isdigit() else None
        if not static_match or amount is None or amount <= 0:
            result.service_lines += 1
            continue

        static_id = static_match.group(1)
        if static_id in by_static:
            by_static[static_id].amount += amount
            if static_id not in result.duplicate_static_ids:
                result.duplicate_static_ids.append(static_id)
            continue

        payment = BulkPayment(
            employee_name=parts[0] or "—",
            static_id=static_id,
            position=parts[2] or "—",
            amount=amount,
        )
        by_static[static_id] = payment
        ordered.append(payment)

    result.payments = ordered
    return result
