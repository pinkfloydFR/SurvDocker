from datetime import datetime, timezone

from survdocker.analyzer import LogEntry, build_export, build_report, copyable_text, group_entries


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


def test_build_export_ranks_by_total_occurrences_across_reports():
    week1 = build_report(
        [
            LogEntry("bookstack", "error one", datetime(2026, 8, 10, 6, 0, tzinfo=timezone.utc)),
            LogEntry("traefik", "warning deprecated config", datetime(2026, 8, 10, 6, 2, tzinfo=timezone.utc)),
        ]
    )
    week2 = build_report(
        [
            LogEntry("bookstack", "error one", datetime(2026, 8, 17, 6, 0, tzinfo=timezone.utc)),
            LogEntry("traefik", "warning deprecated config", datetime(2026, 8, 17, 6, 1, tzinfo=timezone.utc)),
            LogEntry("traefik", "warning deprecated config", datetime(2026, 8, 17, 6, 2, tzinfo=timezone.utc)),
            LogEntry("traefik", "warning deprecated config", datetime(2026, 8, 17, 6, 3, tzinfo=timezone.utc)),
            LogEntry("traefik", "warning deprecated config", datetime(2026, 8, 17, 6, 4, tzinfo=timezone.utc)),
        ]
    )
    export = build_export([("report-2026-08-17", week2), ("report-2026-08-10", week1)])

    assert export["source_reports"] == ["report-2026-08-17", "report-2026-08-10"]
    top = export["problems"][0]
    assert top["container"] == "traefik"
    assert top["total_occurrences"] == 5
    assert top["report_count"] == 2
    assert top["first_seen"] == "2026-08-10T06:02:00+00:00"
    assert top["last_seen"] == "2026-08-17T06:04:00+00:00"
    assert export["problems"][1]["container"] == "bookstack"


def test_build_export_drops_problems_already_fixed_in_latest_report():
    week1 = build_report(
        [
            LogEntry("bookstack", "error one", datetime(2026, 8, 10, 6, 0, tzinfo=timezone.utc)),
            LogEntry("bookstack", "error one", datetime(2026, 8, 10, 6, 1, tzinfo=timezone.utc)),
            LogEntry("traefik", "warning deprecated config", datetime(2026, 8, 10, 6, 2, tzinfo=timezone.utc)),
        ]
    )
    # traefik's warning was fixed after week1 and no longer appears in week2.
    week2 = build_report(
        [
            LogEntry("bookstack", "error one", datetime(2026, 8, 17, 6, 0, tzinfo=timezone.utc)),
            LogEntry("bookstack", "error one", datetime(2026, 8, 17, 6, 1, tzinfo=timezone.utc)),
            LogEntry("bookstack", "error one", datetime(2026, 8, 17, 6, 2, tzinfo=timezone.utc)),
        ]
    )
    export = build_export([("report-2026-08-17", week2), ("report-2026-08-10", week1)])

    containers = [problem["container"] for problem in export["problems"]]
    assert containers == ["bookstack"]
    top = export["problems"][0]
    assert top["total_occurrences"] == 5
    assert top["report_count"] == 2
