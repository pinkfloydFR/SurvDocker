from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlencode, urljoin

import requests


@dataclass(frozen=True)
class LokiLogEntry:
    container: str
    raw: str
    timestamp: datetime | None
    labels: dict[str, str]


def _parse_loki_timestamp(value: str | int | float) -> datetime | None:
    try:
        timestamp_ns = int(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(timestamp_ns / 1_000_000_000, tz=timezone.utc)


def _parse_labels(label_string: str) -> dict[str, str]:
    labels: dict[str, str] = {}
    if not label_string:
        return labels
    for part in label_string.strip("{}").split(","):
        if not part or "=" not in part:
            continue
        key, value = part.split("=", 1)
        labels[key.strip()] = value.strip().strip('"')
    return labels


class LokiClient:
    def __init__(self, base_url: str, timeout_seconds: int = 30, query_limit: int = 50000) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.query_limit = query_limit

    def query_range(self, query: str, start_ns: int, end_ns: int) -> list[LokiLogEntry]:
        params = urlencode({
            "query": query,
            "start": start_ns,
            "end": end_ns,
            "limit": self.query_limit,
            "direction": "forward",
        })
        url = urljoin(self.base_url + "/", f"loki/api/v1/query_range?{params}")
        response = requests.get(url, timeout=self.timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        return self._parse_response(payload)

    def _parse_response(self, payload: dict) -> list[LokiLogEntry]:
        data = payload.get("data", {})
        results = data.get("result", [])
        entries: list[LokiLogEntry] = []
        for stream in results:
            labels = stream.get("stream", {}) or {}
            container = labels.get("container") or labels.get("container_name") or labels.get("container_name_raw") or labels.get("compose_container") or labels.get("job") or "unknown"
            for value in stream.get("values", []):
                if not isinstance(value, list) or len(value) < 2:
                    continue
                timestamp = _parse_loki_timestamp(value[0])
                raw = str(value[1])
                entries.append(LokiLogEntry(container=container, raw=raw, timestamp=timestamp, labels={k: str(v) for k, v in labels.items()}))
        return entries


def default_query(job_label: str) -> str:
    return f'{{job="{job_label}"}}'
