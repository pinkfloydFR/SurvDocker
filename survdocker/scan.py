from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .analyzer import LogEntry, build_report
from .filters import FilterConfig
from .loki import LokiClient, default_query
from .storage import save_report, load_json, save_json


@dataclass(frozen=True)
class ScanResult:
    report: dict
    report_path: Path | None
    status: str
    message: str


def parse_lookback(value: str) -> timedelta:
    value = value.strip().lower()
    if value.endswith("d"):
        return timedelta(days=int(value[:-1]))
    if value.endswith("h"):
        return timedelta(hours=int(value[:-1]))
    if value.endswith("m"):
        return timedelta(minutes=int(value[:-1]))
    return timedelta(days=7)


def compute_period(now: datetime, lookback: str, timezone_name: str) -> tuple[datetime, datetime]:
    try:
        tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        tz = timezone.utc
    localized_now = now.astimezone(tz)
    start = localized_now - parse_lookback(lookback)
    return start.astimezone(timezone.utc), localized_now.astimezone(timezone.utc)


def run_scan(settings, report_date: str | None = None) -> ScanResult:
    filter_config = FilterConfig.from_settings(settings)
    now = datetime.now(timezone.utc)
    start, end = compute_period(now, settings.scan.lookback, settings.scan.timezone)
    report_date = report_date or end.astimezone(ZoneInfo(settings.scan.timezone)).date().isoformat()
    report_meta = {
        "generated_at": now.isoformat(),
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "containers": [],
        "state": "empty",
    }

    try:
        client = LokiClient(settings.loki.base_url, timeout_seconds=settings.loki.query_timeout_seconds, query_limit=settings.loki.query_limit)
        raw_entries = client.query_range(default_query(settings.loki.job_label), int(start.timestamp() * 1_000_000_000), int(end.timestamp() * 1_000_000_000))
        entries: list[LogEntry] = []
        per_container_counts: dict[str, int] = {}
        for entry in raw_entries:
            container_name = entry.container or "unknown"
            per_container_counts.setdefault(container_name, 0)
            if per_container_counts[container_name] >= settings.scan.max_log_lines_per_container:
                continue
            per_container_counts[container_name] += 1
            entries.append(LogEntry(container=container_name, raw=entry.raw, timestamp=entry.timestamp))
        report = build_report(entries, config=filter_config, max_groups_per_container=settings.scan.max_error_groups_per_container, max_examples=settings.scan.max_examples_per_error)
        report["generated_at"] = now.isoformat()
        report["period"] = {"start": start.isoformat(), "end": end.isoformat()}
        report["state"] = "ok"
        report["source"] = {"loki": settings.loki.base_url, "query": default_query(settings.loki.job_label)}
        path = save_report(settings.data_dir, report, report_date, retention_reports=settings.scan.retention_reports)
        save_json(settings.data_dir / "last-scan.json", {"status": "ok", "report_path": str(path), "timestamp": now.isoformat()})
        return ScanResult(report=report, report_path=path, status="ok", message="scan completed")
    except Exception as exc:
        report = dict(report_meta)
        report["state"] = "loki_unavailable"
        report["error"] = str(exc)
        save_json(settings.data_dir / "last-scan.json", {"status": "error", "error": str(exc), "timestamp": now.isoformat()})
        return ScanResult(report=report, report_path=None, status="error", message=str(exc))
