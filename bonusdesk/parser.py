from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from urllib.parse import urlsplit, urlunsplit


COUNT_RE = re.compile(
    r"^(?P<name>.+?)\s*\((?:кол\s*-?\s*во|количество)\)\s*[.:]?\s*(?P<value>.*)$",
    re.IGNORECASE,
)
EVIDENCE_RE = re.compile(
    r"^(?P<name>.+?)\s*\((?:док\s*-?\s*ва|доказательства?)\)\s*[.:]?\s*(?P<value>.*)$",
    re.IGNORECASE,
)
URL_RE = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)


@dataclass(slots=True)
class ParsedItem:
    name: str
    claimed_count: int
    evidence_url: str = ""


@dataclass(slots=True)
class ParsedReport:
    employee_name: str = ""
    static_id: str = ""
    primary_department: str = ""
    secondary_department: str = ""
    items: list[ParsedItem] = field(default_factory=list)
    source_text: str = ""

    @property
    def fingerprint(self) -> str:
        parts = [
            self.employee_name.strip().casefold(),
            self.static_id.strip(),
            self.primary_department.strip().casefold(),
            self.secondary_department.strip().casefold(),
        ]
        parts.extend(
            f"{normalize_work_name(item.name)}|{item.claimed_count}|{'|'.join(normalize_url(url) for url in extract_urls(item.evidence_url))}"
            for item in self.items
        )
        return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


class ReportParseError(ValueError):
    pass


def _clean_label(value: str) -> str:
    value = value.strip().strip("*_`").rstrip(":").strip()
    return re.sub(r"\s+", " ", value)


def _next_value(lines: list[str], index: int, inline: str = "") -> tuple[str, int]:
    if inline.strip():
        return inline.strip(), index
    cursor = index + 1
    while cursor < len(lines) and not lines[cursor].strip():
        cursor += 1
    return (lines[cursor].strip() if cursor < len(lines) else ""), cursor


def _metadata_value(lines: list[str], patterns: tuple[str, ...]) -> str:
    for index, line in enumerate(lines):
        normalized = _clean_label(line).casefold()
        for pattern in patterns:
            if normalized == pattern.casefold():
                value, _ = _next_value(lines, index)
                return value
            if normalized.startswith(pattern.casefold() + " "):
                return line[len(pattern):].strip(" :")
    return ""


def normalize_url(url: str) -> str:
    url = url.strip().rstrip(".,;)")
    if not url:
        return ""
    try:
        parts = urlsplit(url)
        host = parts.netloc.casefold()
        path = parts.path.rstrip("/")
        return urlunsplit((parts.scheme.casefold(), host, path, parts.query, ""))
    except ValueError:
        return url


def extract_urls(value: str) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for match in URL_RE.findall(value or ""):
        url = match.strip().rstrip(".,;)")
        normalized = normalize_url(url)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(url)
    return result


def normalize_work_name(name: str) -> str:
    value = _clean_label(name).casefold().replace("ё", "е")
    value = re.sub(r"[^a-zа-я0-9]+", " ", value, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", value).strip()


def parse_report(text: str) -> ParsedReport:
    if not text or not text.strip():
        raise ReportParseError("Буфер обмена пуст.")

    lines = [_clean_label(line.replace("\u200b", "")) for line in text.replace("\r\n", "\n").split("\n")]
    report = ParsedReport(
        employee_name=_metadata_value(lines, ("Имя фамилия", "Ваше имя и фамилия")),
        static_id=_metadata_value(lines, ("Ваш Static ID.", "Ваш Static ID", "Static ID")),
        primary_department=_metadata_value(lines, ("Ваш основной отдел", "Основной отдел")),
        secondary_department=_metadata_value(lines, ("Ваш дополнительный отдел", "Дополнительный отдел")),
        source_text=text.strip(),
    )

    pending: dict[str, ParsedItem] = {}
    index = 0
    while index < len(lines):
        line = lines[index]
        count_match = COUNT_RE.match(line)
        evidence_match = EVIDENCE_RE.match(line)
        if count_match:
            raw_value, next_index = _next_value(lines, index, count_match.group("value"))
            number_match = re.search(r"\d+", raw_value.replace(" ", ""))
            if number_match:
                name = _clean_label(count_match.group("name"))
                key = normalize_work_name(name)
                pending[key] = ParsedItem(name=name, claimed_count=int(number_match.group()))
            index = max(index, next_index)
        elif evidence_match:
            name = _clean_label(evidence_match.group("name"))
            key = normalize_work_name(name)
            evidence_lines = [evidence_match.group("value")]
            cursor = index + 1
            while cursor < len(lines):
                candidate = lines[cursor]
                if COUNT_RE.match(candidate) or EVIDENCE_RE.match(candidate):
                    break
                evidence_lines.append(candidate)
                cursor += 1
            urls = extract_urls("\n".join(evidence_lines))
            if key not in pending:
                pending[key] = ParsedItem(name=name, claimed_count=0)
            pending[key].evidence_url = "\n".join(urls)
            index = max(index, cursor - 1)
        index += 1

    report.items = list(pending.values())
    missing = []
    if not report.employee_name:
        missing.append("имя сотрудника")
    if not re.fullmatch(r"\d{1,12}", report.static_id):
        missing.append("корректный Static ID")
    if not report.items:
        missing.append("хотя бы один вид работы")
    if missing:
        raise ReportParseError("Не удалось определить: " + ", ".join(missing) + ".")
    return report
