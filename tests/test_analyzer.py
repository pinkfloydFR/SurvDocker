from datetime import datetime, timezone

from survdocker.analyzer import LogEntry, build_report, copyable_text, group_entries


def test_grouping_and_top_results():
    entries = [
        LogEntry("traefik", "error backend unavailable", datetime(2026, 8, 17, 6, 0, tzinfo=timezone.utc)),
        LogEntry("traefik", "error backend unavailable", datetime(2026, 8, 17, 6, 1, tzinfo=timezone.utc)),
        LogEntry("traefik", "warning deprecated config", datetime(2026, 8, 17, 6, 2, tzinfo=timezone.utc)),
        LogEntry("traefik", "warning deprecated config", datetime(2026, 8, 17, 6, 3, tzinfo=timezone.utc)),
        LogEntry("traefik", "warning deprecated config", datetime(2026, 8, 17, 6, 4, tzinfo=timezone.utc)),
    ]
    groups = group_entries(entries, max_examples=2)
    assert len(groups) == 2
    assert groups[0].occurrences == 3


def test_examples_limit_and_copy_text():
    entries = [
        LogEntry("bookstack", "error one", datetime(2026, 8, 17, 6, 0, tzinfo=timezone.utc)),
        LogEntry("bookstack", "error one", datetime(2026, 8, 17, 6, 1, tzinfo=timezone.utc)),
        LogEntry("bookstack", "error one", datetime(2026, 8, 17, 6, 2, tzinfo=timezone.utc)),
    ]
    report = build_report(entries, max_groups_per_container=5, max_examples=2)
    group = report["containers"][0]["error_groups"][0]
    assert group["examples_complete"] is False
    copied = copyable_text(group)
    assert "Container: bookstack" in copied
    assert "Original lines:" in copied
