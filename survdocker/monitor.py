from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import os
import socket
from pathlib import Path
from typing import Any

import yaml

from .storage import load_json, save_json
from .telegram import send_message


CRITICAL_STATES = {"exited", "dead", "restarting", "unhealthy"}
DEPENDENCY_PATTERNS = [
    "connection refused",
    "connection reset",
    "no route to host",
    "host is unreachable",
    "network is unreachable",
    "name or service not known",
    "temporary failure in name resolution",
    "could not connect",
    "failed to connect",
    "connection timed out",
    "i/o timeout",
    "server unavailable",
    "backend unavailable",
    "service unavailable",
    "database unavailable",
    "database connection failed",
    "unable to connect to database",
    "connection to database refused",
    "could not connect to server",
    "postgresql connection refused",
    "mysql connection refused",
    "mariadb connection refused",
    "redis connection refused",
    "redis: connection error",
    "storage backend unavailable",
    "session backend unavailable",
]


@dataclass(frozen=True)
class CriticalAlert:
    key: str
    container: str
    alert_type: str
    state: str
    reason: str
    last_lines: list[str]
    restart_count: int = 0
    first_seen: str | None = None
    last_seen: str | None = None


def _connect_unix_http(socket_path: str, method: str, path: str, body: bytes | None = None, headers: dict[str, str] | None = None) -> tuple[int, dict[str, str], bytes]:
    headers = headers or {}
    payload = body or b""
    request_headers = [
        f"{method} {path} HTTP/1.1",
        "Host: localhost",
        f"Content-Length: {len(payload)}",
        "Connection: close",
    ]
    request_headers.extend(f"{key}: {value}" for key, value in headers.items())
    request_bytes = ("\r\n".join(request_headers) + "\r\n\r\n").encode("utf-8") + payload
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.connect(socket_path)
        sock.sendall(request_bytes)
        chunks = []
        while True:
            part = sock.recv(65536)
            if not part:
                break
            chunks.append(part)
    raw = b"".join(chunks)
    header_blob, _, body_blob = raw.partition(b"\r\n\r\n")
    header_lines = header_blob.split(b"\r\n")
    status = int(header_lines[0].split()[1])
    response_headers: dict[str, str] = {}
    for line in header_lines[1:]:
        if b":" not in line:
            continue
        key, value = line.split(b":", 1)
        response_headers[key.decode().strip().lower()] = value.decode().strip()
    return status, response_headers, body_blob


def docker_api_request(socket_path: str, path: str) -> Any:
    status, _, body = _connect_unix_http(socket_path, "GET", path)
    if status >= 400:
        raise RuntimeError(f"Docker API returned HTTP {status}")
    return json.loads(body.decode("utf-8"))


def docker_api_request_text(socket_path: str, path: str) -> str:
    status, _, body = _connect_unix_http(socket_path, "GET", path)
    if status >= 400:
        raise RuntimeError(f"Docker API returned HTTP {status}")
    return body.decode("utf-8", errors="replace")


def extract_container_name(container: dict[str, Any]) -> str:
    names = container.get("Names") or []
    if names:
        return str(names[0]).lstrip("/")
    return str(container.get("Name") or container.get("Id") or "unknown")


def detect_dependency_issue(lines: list[str]) -> str | None:
    for line in lines:
        lower = line.lower()
        if any(pattern in lower for pattern in DEPENDENCY_PATTERNS):
            return line
    return None


def count_dependency_matches(lines: list[str]) -> int:
    total = 0
    for line in lines:
        lower = line.lower()
        if any(pattern in lower for pattern in DEPENDENCY_PATTERNS):
            total += 1
    return total


def build_critical_alerts(config: dict[str, Any], containers: list[dict[str, Any]], logs: dict[str, list[str]]) -> list[CriticalAlert]:
    critical_containers = set(config.get("critical_containers", []))
    ignored_containers = set(config.get("ignored_containers", []))
    dependencies = config.get("dependencies", {})
    critical_rules = config.get("critical_alerts", {})
    alerts: list[CriticalAlert] = []
    present_names = {extract_container_name(container) for container in containers}
    for critical_name in critical_containers:
        if critical_name not in present_names and critical_name not in ignored_containers:
            alerts.append(CriticalAlert(key=f"container={critical_name}|type=missing", container=critical_name, alert_type="missing", state="missing", reason="container absent", last_lines=[]))
    for container in containers:
        name = extract_container_name(container)
        if name in ignored_containers:
            continue
        state = str(container.get("State") or "").lower()
        restart_count = int((container.get("RestartCount") or 0))
        status_text = str(container.get("Status") or "")
        lines = logs.get(name, [])[-10:]
        dependency_line = detect_dependency_issue(lines)
        if name in critical_containers and state in CRITICAL_STATES:
            alerts.append(CriticalAlert(key=f"container={name}|state={state}", container=name, alert_type="critical_state", state=state, reason=status_text or state, last_lines=lines, restart_count=restart_count))
            continue
        if restart_count >= int(critical_rules.get("restart_threshold", 3)) and state == "running":
            alerts.append(CriticalAlert(key=f"container={name}|type=restart_spike", container=name, alert_type="restart_spike", state=state, reason="restart loop suspected", last_lines=lines, restart_count=restart_count))
            continue
        if dependency_line and count_dependency_matches(lines) >= int(critical_rules.get("error_threshold", 3)) and (name in critical_containers or name in dependencies):
            reason = dependency_line
            alerts.append(CriticalAlert(key=f"container={name}|type=dependency", container=name, alert_type="dependency", state=state, reason=reason, last_lines=lines, restart_count=restart_count))
    return alerts


def format_alert_message(alert: CriticalAlert, site_url: str) -> str:
    lines = [
        "🚨 ALERTE DOCKER CRITIQUE",
        f"Conteneur : {alert.container}",
        f"État : {alert.state}",
    ]
    if alert.restart_count:
        lines.append(f"Redémarrages : {alert.restart_count}")
    lines.append(f"Cause probable : {alert.reason}")
    if alert.last_lines:
        lines.append("Dernière erreur :")
        lines.extend(alert.last_lines[:5])
    lines.append(f"Rapport : {site_url}")
    return "\n".join(lines)


def format_recovery_message(alert: CriticalAlert) -> str:
    lines = [
        "✅ SERVICE RÉTABLI",
        f"Conteneur : {alert.container}",
        f"Problème : {alert.reason}",
    ]
    if alert.first_seen and alert.last_seen:
        lines.append(f"Durée estimée : {alert.first_seen} -> {alert.last_seen}")
    return "\n".join(lines)


def run_critical_monitor(settings, monitor_config: dict[str, Any], state_path: Path) -> dict[str, Any]:
    socket_path = os.environ.get("DOCKER_SOCKET_PATH", "/var/run/docker.sock")
    try:
        containers = docker_api_request(socket_path, "/containers/json?all=1")
    except Exception as exc:
        return {"status": "error", "message": str(exc), "alerts": []}

    logs: dict[str, list[str]] = {}
    for container in containers:
        name = extract_container_name(container)
        container_id = str(container.get("Id") or "")
        if not container_id:
            logs[name] = []
            continue
        try:
            raw_log = docker_api_request_text(socket_path, f"/containers/{container_id}/logs?stdout=1&stderr=1&tail=25")
            logs[name] = [line for line in raw_log.splitlines() if line.strip()]
        except Exception:
            logs[name] = []

    alerts = build_critical_alerts({
        "critical_containers": settings.critical.critical_containers,
        "ignored_containers": settings.critical.ignored_containers,
        "critical_alerts": settings.critical.critical_alerts,
        "dependencies": settings.critical.dependencies,
    }, containers, logs)
    state = load_json(state_path, {"active_alerts": {}})
    sent_alerts: list[dict[str, Any]] = []
    recovery_alerts: list[dict[str, Any]] = []
    cooldown_seconds = int(settings.critical.critical_alerts.get("notification_cooldown_seconds", 3600))
    now = datetime.now(timezone.utc)
    active_alert_keys = {alert.key for alert in alerts}
    previous_active = dict(state.get("active_alerts", {}))
    for key, payload in list(previous_active.items()):
        if key in active_alert_keys:
            continue
        if settings.critical.critical_alerts.get("notify_resolution", False) and settings.telegram.enabled and settings.telegram.bot_token and settings.telegram.chat_id:
            recovery = CriticalAlert(
                key=key,
                container=str(payload.get("container", key)),
                alert_type=str(payload.get("alert_type", "resolved")),
                state="resolved",
                reason=str(payload.get("alert_type", "resolved")),
                last_lines=[],
                first_seen=payload.get("first_seen"),
                last_seen=payload.get("last_seen"),
            )
            result = send_message(settings.telegram.api_base_url, settings.telegram.bot_token, settings.telegram.chat_id, format_recovery_message(recovery), settings.telegram.thread_id)
            recovery_alerts.append({"key": key, "ok": result.ok, "status_code": result.status_code})
        state.get("active_alerts", {}).pop(key, None)
        state.setdefault("resolved_alerts", {})[key] = {"resolved_at": now.isoformat(), **payload}
    for alert in alerts:
        last_sent = state.get("active_alerts", {}).get(alert.key, {})
        last_sent_at = last_sent.get("last_sent_at")
        if last_sent_at:
            try:
                previous = datetime.fromisoformat(last_sent_at)
            except ValueError:
                previous = None
            if previous and now - previous < timedelta(seconds=cooldown_seconds):
                continue
        if settings.telegram.enabled and settings.telegram.bot_token and settings.telegram.chat_id:
            message = format_alert_message(alert, "https://survdocker.denisflamant.com")
            result = send_message(settings.telegram.api_base_url, settings.telegram.bot_token, settings.telegram.chat_id, message, settings.telegram.thread_id)
            sent_alerts.append({"key": alert.key, "ok": result.ok, "status_code": result.status_code})
            state.setdefault("active_alerts", {})[alert.key] = {"last_sent_at": now.isoformat(), "container": alert.container, "alert_type": alert.alert_type, "first_seen": alert.first_seen, "last_seen": alert.last_seen}
    save_json(state_path, state)
    return {"status": "ok", "alerts": [alert.__dict__ for alert in alerts], "sent": sent_alerts, "resolved": recovery_alerts}


def load_monitor_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
