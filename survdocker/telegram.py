from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class TelegramResult:
    ok: bool
    status_code: int | None
    message: str


def sanitize_message(text: str) -> str:
    redacted = text
    for token in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "password", "token", "secret"):
        redacted = redacted.replace(token, "[redacted]")
    return redacted


def send_message(api_base_url: str, bot_token: str, chat_id: str, text: str, thread_id: str | None = None, timeout: int = 10) -> TelegramResult:
    url = f"{api_base_url.rstrip('/')}/bot{bot_token}/sendMessage"
    payload: dict[str, Any] = {"chat_id": chat_id, "text": sanitize_message(text)}
    if thread_id:
        payload["message_thread_id"] = thread_id
    response = requests.post(url, data=payload, timeout=timeout)
    if response.ok:
        return TelegramResult(ok=True, status_code=response.status_code, message="sent")
    return TelegramResult(ok=False, status_code=response.status_code, message=response.text)
