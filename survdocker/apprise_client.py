from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


@dataclass(frozen=True)
class AppriseResult:
    ok: bool
    status_code: int | None
    message: str


def send_apprise(url: str, title: str, body: str, tag: str | None = None, notify_type: str = "info", timeout: int = 10) -> AppriseResult:
    payload: dict[str, Any] = {"title": title, "body": body, "type": notify_type}
    if tag:
        payload["tag"] = tag
    response = requests.post(url, data=payload, timeout=timeout)
    if response.ok:
        return AppriseResult(ok=True, status_code=response.status_code, message="sent")
    return AppriseResult(ok=False, status_code=response.status_code, message=response.text)
