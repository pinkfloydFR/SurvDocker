from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Iterable

import yaml


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
_EXPLICIT_LEVEL_MAP = {
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
    if not match:
        return None
    return _EXPLICIT_LEVEL_MAP.get(match.group(1).lower())


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
