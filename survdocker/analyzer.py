from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable

from .filters import FilterConfig, classify_level, should_keep_line
from .normalize import normalize_message


@dataclass(frozen=True)
class LogEntry:
    container: str
    raw: str
    timestamp: datetime | None = None


@dataclass
class ErrorGroup:
    container: str
    level: str
    normalized_message: str
    occurrences: int = 0
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    examples: list[str] = field(default_factory=list)
    examples_complete: bool = True

    def add(self, entry: LogEntry, max_examples: int) -> None:
        self.occurrences += 1
        self.first_seen = entry.timestamp if self.first_seen is None or (entry.timestamp and entry.timestamp < self.first_seen) else self.first_seen
        self.last_seen = entry.timestamp if self.last_seen is None or (entry.timestamp and entry.timestamp > self.last_seen) else self.last_seen
        if len(self.examples) < max_examples:
            self.examples.append(entry.raw)
        else:
            self.examples_complete = False


def detect_level(message: str, config: FilterConfig | None = None) -> str:
    return classify_level(message, config)


def group_entries(entries: Iterable[LogEntry], config: FilterConfig | None = None, max_examples: int = 100) -> list[ErrorGroup]:
    config = config or FilterConfig()
    groups: dict[tuple[str, str], ErrorGroup] = {}
    for entry in entries:
        if not should_keep_line(entry.raw, config):
            continue
        normalized = normalize_message(entry.raw)
        level = detect_level(entry.raw, config)
        key = (entry.container, normalized)
        group = groups.get(key)
        if group is None:
            group = ErrorGroup(container=entry.container, level=level, normalized_message=normalized)
            groups[key] = group
        elif level in {"fatal", "error"} and group.level == "warning":
            group.level = level
        group.add(entry, max_examples=max_examples)
    return sorted(groups.values(), key=lambda item: (item.container, -item.occurrences, item.normalized_message))


def build_report(entries: Iterable[LogEntry], config: FilterConfig | None = None, max_groups_per_container: int = 5, max_examples: int = 100) -> dict:
    config = config or FilterConfig()
    grouped = group_entries(entries, config=config, max_examples=max_examples)
    by_container: dict[str, list[ErrorGroup]] = defaultdict(list)
    for group in grouped:
        by_container[group.container].append(group)
    for container in by_container:
        by_container[container] = sorted(by_container[container], key=lambda item: (-item.occurrences, item.normalized_message))[:max_groups_per_container]
    generated_at = datetime.now(timezone.utc).isoformat()
    return {
        "generated_at": generated_at,
        "period": {"start": None, "end": None},
        "containers": [
            {
                "name": container,
                "error_groups": [
                    {
                        "container": group.container,
                        "level": group.level,
                        "normalized_message": group.normalized_message,
                        "occurrences": group.occurrences,
                        "first_seen": group.first_seen.isoformat() if group.first_seen else None,
                        "last_seen": group.last_seen.isoformat() if group.last_seen else None,
                        "examples": list(group.examples),
                        "examples_complete": group.examples_complete,
                    }
                    for group in groups
                ],
            }
            for container, groups in sorted(by_container.items())
        ],
    }


def copyable_text(group: dict, report_period: str | None = None) -> str:
    lines = [
        f"Container: {group['container']}",
        f"Level: {group['level']}",
        f"Occurrences: {group['occurrences']}",
        f"First seen: {group['first_seen']}",
        f"Last seen: {group['last_seen']}",
        f"Normalized pattern: {group['normalized_message']}",
    ]
    if report_period:
        lines.append(f"Period: {report_period}")
    lines.append("Original lines:")
    lines.extend(f"- {line}" for line in group.get("examples", []))
    if not group.get("examples_complete", True):
        lines.append("Examples truncated")
    return "\n".join(lines)


def report_summary(report: dict) -> dict:
    containers = report.get("containers", [])
    total_groups = sum(len(container.get("error_groups", [])) for container in containers)
    total_containers = len(containers)
    return {
        "generated_at": report.get("generated_at"),
        "period": report.get("period", {}),
        "container_count": total_containers,
        "error_container_count": sum(1 for container in containers if container.get("error_groups")),
        "group_count": total_groups,
    }


def format_report_copy(group: dict, report: dict) -> str:
    period = report.get("period", {})
    period_text = f"{period.get('start')} -> {period.get('end')}" if period else None
    return copyable_text(group, report_period=period_text)

