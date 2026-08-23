from __future__ import annotations

from dataclasses import dataclass

from .apprise_client import send_apprise
from .telegram import send_message


@dataclass(frozen=True)
class NotifyResult:
    channel: str
    ok: bool
    status_code: int | None
    message: str


def notifications_configured(settings) -> bool:
    telegram_ready = bool(settings.telegram.bot_token and settings.telegram.chat_id)
    apprise_ready = bool(settings.apprise.url)
    return telegram_ready or apprise_ready


def notify(settings, title: str, text: str) -> list[NotifyResult]:
    results: list[NotifyResult] = []
    if settings.telegram.bot_token and settings.telegram.chat_id:
        result = send_message(settings.telegram.api_base_url, settings.telegram.bot_token, settings.telegram.chat_id, text, settings.telegram.thread_id)
        results.append(NotifyResult(channel="telegram", ok=result.ok, status_code=result.status_code, message=result.message))
    if settings.apprise.url:
        result = send_apprise(settings.apprise.url, title, text, settings.apprise.tag)
        results.append(NotifyResult(channel="apprise", ok=result.ok, status_code=result.status_code, message=result.message))
    return results
