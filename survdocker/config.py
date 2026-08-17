from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class LokiSettings:
    base_url: str
    query_timeout_seconds: int
    query_limit: int
    job_label: str
    retention_days: int


@dataclass(frozen=True)
class ScanSettings:
    day: int
    time: str
    lookback: str
    timezone: str
    max_log_lines_per_container: int
    max_examples_per_error: int
    max_error_groups_per_container: int
    retention_reports: int


@dataclass(frozen=True)
class TelegramSettings:
    enabled: bool
    bot_token: str
    chat_id: str
    thread_id: str | None
    api_base_url: str


@dataclass(frozen=True)
class FilterSettings:
    ignore_patterns: list[str]
    keep_patterns: list[str]
    warning_patterns: list[str]
    enable_default_ignore: bool
    enable_default_keep: bool
    enable_default_warning: bool


@dataclass(frozen=True)
class CriticalSettings:
    ignored_containers: list[str]
    critical_containers: list[str]
    critical_alerts: dict[str, Any]
    dependencies: dict[str, list[str]]


@dataclass(frozen=True)
class Settings:
    root_dir: Path
    data_dir: Path
    config_dir: Path
    runtime_config_dir: Path
    config_file: Path
    host: str
    port: int
    scan_token: str
    traffic_middleware: str
    loki: LokiSettings
    scan: ScanSettings
    telegram: TelegramSettings
    filters: FilterSettings
    critical: CriticalSettings
    timezone: str


@dataclass(frozen=True)
class GeneratedConfigPaths:
    loki_config_path: Path
    alloy_config_path: Path


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_settings() -> Settings:
    root_dir = Path.cwd()
    data_dir = Path(os.environ.get("SURVDOCKER_DATA_DIR", root_dir / "survdocker" / "data"))
    config_dir = Path(os.environ.get("SURVDOCKER_CONFIG_DIR", root_dir / "survdocker" / "config"))
    runtime_config_dir = Path(os.environ.get("SURVDOCKER_SYSTEM_CONFIG_DIR", root_dir / "survdocker" / "system"))
    config_file = Path(os.environ.get("SURVDOCKER_CONFIG_FILE", config_dir / "survdocker.yml"))
    config_dir.mkdir(parents=True, exist_ok=True)
    runtime_config_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "reports").mkdir(parents=True, exist_ok=True)

    config = _read_yaml(config_file)
    app_config = config.get("app", {})
    loki_config = config.get("loki", {})
    scan_config = config.get("scan", {})
    telegram_config = config.get("telegram", {})
    filters_config = config.get("filters", {})
    critical_config = config.get("critical", {})

    host = os.environ.get("SURVDOCKER_HOST", app_config.get("host", "0.0.0.0"))
    port = int(os.environ.get("SURVDOCKER_PORT", app_config.get("port", 8080)))
    scan_token = os.environ.get("SURVDOCKER_SCAN_TOKEN", app_config.get("scan_token", "change-me"))
    traffic_middleware = os.environ.get("TRAEFIK_AUTH_MIDDLEWARE", app_config.get("traffic_middleware", ""))
    timezone = os.environ.get("TIMEZONE", app_config.get("timezone", "Europe/Paris"))

    loki = LokiSettings(
        base_url=os.environ.get("LOKI_BASE_URL", loki_config.get("base_url", "http://loki:3100")),
        query_timeout_seconds=int(os.environ.get("LOKI_QUERY_TIMEOUT_SECONDS", loki_config.get("query_timeout_seconds", 30))),
        query_limit=int(os.environ.get("LOKI_QUERY_LIMIT", loki_config.get("query_limit", 50000))),
        job_label=os.environ.get("LOKI_JOB_LABEL", loki_config.get("job_label", "docker")),
        retention_days=int(os.environ.get("LOKI_RETENTION_DAYS", loki_config.get("retention_days", 30))),
    )
    scan = ScanSettings(
        day=int(os.environ.get("SCAN_DAY", scan_config.get("day", 1))),
        time=os.environ.get("SCAN_TIME", scan_config.get("time", "06:00")),
        lookback=os.environ.get("SCAN_LOOKBACK", scan_config.get("lookback", "7d")),
        timezone=timezone,
        max_log_lines_per_container=int(os.environ.get("MAX_LOG_LINES_PER_CONTAINER", scan_config.get("max_log_lines_per_container", 50000))),
        max_examples_per_error=int(os.environ.get("MAX_EXAMPLES_PER_ERROR", scan_config.get("max_examples_per_error", 100))),
        max_error_groups_per_container=int(os.environ.get("MAX_ERROR_GROUPS_PER_CONTAINER", scan_config.get("max_error_groups_per_container", 5))),
        retention_reports=int(os.environ.get("REPORT_RETENTION_COUNT", scan_config.get("retention_reports", 4))),
    )
    telegram = TelegramSettings(
        enabled=_env_bool("TELEGRAM_ENABLED", telegram_config.get("enabled", False)),
        bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", telegram_config.get("bot_token", "")),
        chat_id=os.environ.get("TELEGRAM_CHAT_ID", telegram_config.get("chat_id", "")),
        thread_id=os.environ.get("TELEGRAM_THREAD_ID", telegram_config.get("thread_id")),
        api_base_url=os.environ.get("TELEGRAM_API_BASE_URL", telegram_config.get("api_base_url", "https://api.telegram.org")),
    )

    filters = FilterSettings(
        ignore_patterns=list(filters_config.get("ignore_patterns", [])),
        keep_patterns=list(filters_config.get("keep_patterns", [])),
        warning_patterns=list(filters_config.get("warning_patterns", [])),
        enable_default_ignore=bool(filters_config.get("enable_default_ignore", True)),
        enable_default_keep=bool(filters_config.get("enable_default_keep", True)),
        enable_default_warning=bool(filters_config.get("enable_default_warning", True)),
    )
    critical = CriticalSettings(
        ignored_containers=list(critical_config.get("ignored_containers", [])),
        critical_containers=list(critical_config.get("critical_containers", [])),
        critical_alerts=dict(critical_config.get("critical_alerts", {})),
        dependencies={key: list(value) for key, value in (critical_config.get("dependencies", {}) or {}).items()},
    )

    return Settings(
        root_dir=root_dir,
        data_dir=data_dir,
        config_dir=config_dir,
        runtime_config_dir=runtime_config_dir,
        config_file=config_file,
        host=host,
        port=port,
        scan_token=scan_token,
        traffic_middleware=traffic_middleware,
        loki=loki,
        scan=scan,
        telegram=telegram,
        filters=filters,
        critical=critical,
        timezone=timezone,
    )


def generated_config_paths(settings: Settings) -> GeneratedConfigPaths:
    runtime_config_dir = getattr(settings, "runtime_config_dir", None) or getattr(settings, "config_dir")
    return GeneratedConfigPaths(
        loki_config_path=runtime_config_dir / "loki-config.yml",
        alloy_config_path=runtime_config_dir / "alloy.alloy",
    )

