from __future__ import annotations

import json
from dataclasses import dataclass

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest


from .version import CURRENT_VERSION, version_tuple


REPOSITORY_URL = "https://github.com/flaunti/BonusDesk"
LATEST_RELEASE_API = "https://api.github.com/repos/flaunti/BonusDesk/releases/latest"


@dataclass(slots=True)
class UpdateInfo:
    current_version: str
    latest_version: str
    release_url: str
    is_newer: bool


class UpdateChecker(QObject):
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.manager = QNetworkAccessManager(self)

    def check(self) -> None:
        request = QNetworkRequest(QUrl(LATEST_RELEASE_API))
        request.setRawHeader(b"Accept", b"application/vnd.github+json")
        request.setRawHeader(b"User-Agent", b"BonusDesk-Update-Checker")
        request.setAttribute(QNetworkRequest.RedirectPolicyAttribute, QNetworkRequest.NoLessSafeRedirectPolicy)
        reply = self.manager.get(request)
        reply.finished.connect(lambda reply=reply: self._handle_reply(reply))

    def _handle_reply(self, reply: QNetworkReply) -> None:
        try:
            if reply.error() != QNetworkReply.NoError:
                self.failed.emit(reply.errorString())
                return
            payload = json.loads(bytes(reply.readAll()).decode("utf-8"))
            latest = str(payload.get("tag_name") or payload.get("name") or "").strip().lstrip("vV")
            release_url = str(payload.get("html_url") or REPOSITORY_URL + "/releases/latest")
            if not latest:
                self.failed.emit("В ответе GitHub не указана версия релиза.")
                return
            self.finished.emit(
                UpdateInfo(
                    current_version=CURRENT_VERSION,
                    latest_version=latest,
                    release_url=release_url,
                    is_newer=version_tuple(latest) > version_tuple(CURRENT_VERSION),
                )
            )
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
            self.failed.emit(f"Некорректный ответ GitHub: {exc}")
        finally:
            reply.deleteLater()
