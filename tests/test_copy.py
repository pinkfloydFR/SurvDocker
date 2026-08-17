from datetime import datetime, timezone

from survdocker.analyzer import LogEntry, build_report, format_report_copy


def test_copy_text_contains_exact_lines():
    entries = [LogEntry("authelia_pf", "error initializing session backend: redis connection error", datetime(2026, 8, 17, 6, 0, tzinfo=timezone.utc))]
    report = build_report(entries, max_examples=5)
    group = report["containers"][0]["error_groups"][0]
    copied = format_report_copy(group, report)
    assert "authelia_pf" in copied
    assert "redis connection error" in copied
    assert "Original lines:" in copied
