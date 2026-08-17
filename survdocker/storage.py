from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


def latest_report_path(data_dir: Path) -> Path:
    return data_dir / "latest-report.json"


def report_history_dir(data_dir: Path) -> Path:
    return data_dir / "reports"


def save_report(data_dir: Path, report: dict, report_date: str, retention_reports: int = 4) -> Path:
    history_dir = report_history_dir(data_dir)
    history_dir.mkdir(parents=True, exist_ok=True)
    history_path = history_dir / f"report-{report_date}.json"
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    history_path.write_text(payload, encoding="utf-8")
    latest_report_path(data_dir).write_text(payload, encoding="utf-8")
    prune_reports(history_dir, retention_reports)
    return history_path


def load_report(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_reports(data_dir: Path) -> list[Path]:
    history_dir = report_history_dir(data_dir)
    if not history_dir.exists():
        return []
    return sorted(history_dir.glob("report-*.json"), reverse=True)


def prune_reports(history_dir: Path, retention_reports: int) -> None:
    reports = sorted(history_dir.glob("report-*.json"), reverse=True)
    for path in reports[retention_reports:]:
        path.unlink(missing_ok=True)


def save_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json(path: Path, default: dict | None = None) -> dict:
    if not path.exists():
        return default or {}
    return json.loads(path.read_text(encoding="utf-8"))

