from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Iterable

import yaml

from .normalize import strip_ansi


DEFAULT_IGNORE_PATTERNS = [
    r"status_code=(200|204|301|302|401)",
    r"robots\.txt",
    r"healthcheck",
    r"readiness",
    r"liveness",
    r"/api/health",
    r"/ping",
    r"Access to .* is not authorized",
    r"unauthorized",
]

DEFAULT_KEEP_PATTERNS = [
    r"error",
    r"\bfatal\b",
    r"panic",
    r"exception",
    r"failed",
    r"failure",
    r"\btimeout\b",
    r"connection refused",
    r"permission denied",
    r"database locked",
    r"out of memory",
    r"crashed",
    r"restart",
]

DEFAULT_WARNING_PATTERNS = [r"deprecated", r"warning", r"invalid configuration", r"unknown field"]

_EXPLICIT_LEVEL_RE = re.compile(r'(?:\blevel=|"level"\s*:\s*)"?(\w+)"?', re.IGNORECASE)
# Level written as a line prefix rather than a `level=` field. Only the first
# few tokens are looked at, so a message body mentioning "error" is not
# mistaken for a level. Tried in order:
_PREFIX_LEVEL_RES = [
    # Redis: `1:M 22 Sep 2026 02:31:23.530 * ...` (`.` debug, `-` verbose,
    # `*` notice, `#` warning).
    re.compile(r"^\d+:[MSCX] \d{1,2} \w{3} \d{4} [\d:.]+ ([.*#-]) "),
    # Bazarr: `2026-09-26 06:57:33,001 - root   (734ccebb0b30) :  INFO (...`
    re.compile(r"^\S+ \S+ - \S+\s+\(\w+\)\s*:\s+(DEBUG|INFO|WARNING|ERROR|CRITICAL)\b"),
    # Bracketed, any case, optionally `module:level`: `[...] [WARNING]` (Python
    # logging), `[...] [12266] [INFO]` (gunicorn), `[Warn]` (*arr),
    # `2026-09-23  7:51:57 0 [Warning]` (MariaDB), `[error]` (nginx),
    # `[php:warn]` (Apache).
    re.compile(
        r"^(?:\S+\s+){0,4}?\[(?:[\w-]+:)?(trace|trc|debug|dbg|info|inf|note|notice|warning|warn|wrn|error|err|critical|crit|fatal|ftl|panic)\]",
        re.IGNORECASE,
    ),
    # Bare uppercase word: `INFO: GeoBlock: ...` (Traefik plugins),
    # `10:49AM ERR ...` (zerolog console: Traefik, Sablier), `... ERROR [openvpn]`
    # (gluetun), `UTC [pid] FATAL:` (Postgres).
    re.compile(
        r"^(?:\S+\s+){0,4}?(TRACE|TRC|DEBUG|DBG|INFO|INF|NOTICE|WARNING|WARN|WRN|ERROR|ERR|CRITICAL|CRIT|FATAL|FTL|PANIC|PNC):?(?:\s|$)"
    ),
]
_EXPLICIT_LEVEL_MAP = {
    ".": "unknown",
    "-": "unknown",
    "*": "unknown",
    "#": "warning",
    "note": "unknown",
    "trc": "unknown",
    "dbg": "unknown",
    "inf": "unknown",
    "notice": "unknown",
    "wrn": "warning",
    "ftl": "fatal",
    "pnc": "fatal",
    "fatal": "fatal",
    "panic": "fatal",
    "crit": "fatal",
    "critical": "fatal",
    "error": "error",
    "err": "error",
    "warn": "warning",
    "warning": "warning",
    "info": "unknown",
    "informational": "unknown",
    "debug": "unknown",
    "trace": "unknown",
}


def _explicit_level(line: str) -> str | None:
    """Read an explicit structured `level=` field (e.g. Alloy/Loki's own Go
    logs) and map it to a report level. Keyword search over the raw line
    otherwise misclassifies negated phrasing like `level=info msg="node
    exited without error"` as an error just because "error" appears as a
    substring. Returns None when there is no recognizable explicit level, so
    callers fall back to the keyword heuristics below.
    """
    match = _EXPLICIT_LEVEL_RE.search(line)
    if match:
        level = _EXPLICIT_LEVEL_MAP.get(match.group(1).lower())
        if level is not None:
            return level
    line = strip_ansi(line)
    for pattern in _PREFIX_LEVEL_RES:
        match = pattern.match(line)
        if match:
            return _EXPLICIT_LEVEL_MAP.get(match.group(1).lower())
    return None


@dataclass
class FilterConfig:
    ignore_patterns: list[str] = field(default_factory=lambda: list(DEFAULT_IGNORE_PATTERNS))
    keep_patterns: list[str] = field(default_factory=lambda: list(DEFAULT_KEEP_PATTERNS))
    warning_patterns: list[str] = field(default_factory=lambda: list(DEFAULT_WARNING_PATTERNS))
    enable_default_ignore: bool = True
    enable_default_keep: bool = True
    enable_default_warning: bool = True

    @classmethod
    def from_settings(cls, settings) -> "FilterConfig":
        filters = getattr(settings, "filters", None)
        if filters is None:
            return cls()
        return cls(
            ignore_patterns=list(filters.ignore_patterns),
            keep_patterns=list(filters.keep_patterns),
            warning_patterns=list(filters.warning_patterns),
            enable_default_ignore=filters.enable_default_ignore,
            enable_default_keep=filters.enable_default_keep,
            enable_default_warning=filters.enable_default_warning,
        )


def load_filter_config(path: Path) -> FilterConfig:
    if not path.exists():
        return FilterConfig()
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return FilterConfig(
        ignore_patterns=list(payload.get("ignore_patterns", DEFAULT_IGNORE_PATTERNS)),
        keep_patterns=list(payload.get("keep_patterns", DEFAULT_KEEP_PATTERNS)),
        warning_patterns=list(payload.get("warning_patterns", DEFAULT_WARNING_PATTERNS)),
        enable_default_ignore=bool(payload.get("enable_default_ignore", True)),
        enable_default_keep=bool(payload.get("enable_default_keep", True)),
        enable_default_warning=bool(payload.get("enable_default_warning", True)),
    )


def _matches_any(patterns: Iterable[str], line: str) -> bool:
    return any(re.search(pattern, line, re.IGNORECASE) for pattern in patterns)


def should_keep_line(line: str, config: FilterConfig | None = None) -> bool:
    config = config or FilterConfig()
    ignore_patterns = config.ignore_patterns if config.enable_default_ignore else []
    if _matches_any(ignore_patterns, line):
        return False
    explicit_level = _explicit_level(line)
    if explicit_level == "unknown":
        # An explicit level=info/debug/trace field is a stronger signal than a
        # keyword substring match (e.g. "error" inside "without error").
        return False
    if explicit_level in ("fatal", "error", "warning"):
        return True
    keep_patterns = config.keep_patterns if config.enable_default_keep else []
    warning_patterns = config.warning_patterns if config.enable_default_warning else []
    return _matches_any(keep_patterns + warning_patterns, line)


def classify_level(line: str, config: FilterConfig | None = None) -> str:
    config = config or FilterConfig()
    explicit_level = _explicit_level(line)
    if explicit_level is not None:
        return explicit_level
    if re.search(r"\bfatal\b|panic", line, re.IGNORECASE):
        return "fatal"
    if re.search(r"error|failed|failure|exception|connection refused|\btimeout\b|permission denied|database locked|out of memory|crashed", line, re.IGNORECASE):
        return "error"
    warning_patterns = config.warning_patterns if config.enable_default_warning else []
    if _matches_any(warning_patterns, line):
        return "warning"
    return "unknown"
