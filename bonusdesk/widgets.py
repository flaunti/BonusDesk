from __future__ import annotations

from html import escape
from urllib.parse import urlsplit

from PySide6.QtCore import Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSpinBox, QVBoxLayout, QWidget


def money(value: int) -> str:
    return f"{int(value):,}".replace(",", " ") + " $"


class NoWheelSpinBox(QSpinBox):
    """Spin box that cannot be changed accidentally while scrolling a page."""

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 - Qt API name
        event.ignore()


class Card(QFrame):
    def __init__(self, parent: QWidget | None = None, margins: tuple[int, int, int, int] = (16, 16, 16, 16)):
        super().__init__(parent)
        self.setObjectName("card")
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(*margins)
        self.box.setSpacing(10)


class StatCard(Card):
    def __init__(self, title: str, value: str, accent: bool = False):
        super().__init__()
        title_label = QLabel(title)
        title_label.setObjectName("muted")
        value_label = QLabel(value)
        value_label.setStyleSheet("font-size: 20px; font-weight: 800; color: %s" % ("#2563eb" if accent else "#162033"))
        self.value_label = value_label
        self.box.addWidget(title_label)
        self.box.addWidget(value_label)


class EvidenceLinks(QWidget):
    """Compact list of real, clickable proof URLs."""

    def __init__(self, urls: list[str], parent: QWidget | None = None):
        super().__init__(parent)
        box = QVBoxLayout(self)
        box.setContentsMargins(6, 4, 6, 4)
        box.setSpacing(2)
        if not urls:
            empty = QLabel("Нет ссылки")
            empty.setObjectName("muted")
            box.addWidget(empty)
            return
        for index, url in enumerate(urls, start=1):
            parsed = urlsplit(url)
            compact = parsed.netloc or url
            if len(urls) == 1 and parsed.path and parsed.path != "/":
                tail = parsed.path.rstrip("/").rsplit("/", 1)[-1]
                if tail:
                    compact += f"/{tail}"
            if len(compact) > 25:
                compact = compact[:22] + "…"
            prefix = f"{index}. " if len(urls) > 1 else ""
            link = QLabel(f'<a href="{escape(url, quote=True)}">{prefix}{escape(compact)} ↗</a>')
            link.setObjectName("evidenceLink")
            link.setOpenExternalLinks(True)
            link.setTextInteractionFlags(Qt.TextBrowserInteraction)
            link.setToolTip(url)
            box.addWidget(link)


def page_header(title: str, subtitle: str = "") -> tuple[QWidget, QHBoxLayout]:
    wrapper = QWidget()
    layout = QHBoxLayout(wrapper)
    layout.setContentsMargins(0, 0, 0, 0)
    text = QVBoxLayout()
    heading = QLabel(title)
    heading.setObjectName("pageTitle")
    text.addWidget(heading)
    if subtitle:
        caption = QLabel(subtitle)
        caption.setObjectName("muted")
        text.addWidget(caption)
    layout.addLayout(text)
    layout.addStretch(1)
    return wrapper, layout


def label_pair(title: str, value: str) -> QWidget:
    wrapper = QWidget()
    box = QVBoxLayout(wrapper)
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(2)
    key = QLabel(title)
    key.setObjectName("muted")
    val = QLabel(value or "—")
    val.setTextInteractionFlags(Qt.TextSelectableByMouse)
    box.addWidget(key)
    box.addWidget(val)
    return wrapper
