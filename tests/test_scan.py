from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from survdocker import scan


class DummyLokiClient:
    def __init__(self, *args, **kwargs):
        pass

    def query_range(self, query, start_ns, end_ns):
        return [
            SimpleNamespace(container="traefik", raw="error backend unavailable", timestamp=None),
            SimpleNamespace(container="traefik", raw="error backend unavailable", timestamp=None),
            SimpleNamespace(container="traefik", raw="error backend unavailable", timestamp=None),
            SimpleNamespace(container="bookstack", raw="fatal startup failure", timestamp=None),
        ]


def test_scan_respects_per_container_limit(monkeypatch, tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (tmp_path / "data").mkdir()
    (config_dir / "filters.yml").write_text("", encoding="utf-8")
    settings = SimpleNamespace(
        data_dir=tmp_path / "data",
        config_dir=config_dir,
        loki=SimpleNamespace(base_url="http://loki:3100", query_timeout_seconds=1, query_limit=1000, job_label="docker"),
        scan=SimpleNamespace(lookback="7d", timezone="UTC", max_log_lines_per_container=2, max_examples_per_error=10, max_error_groups_per_container=5, retention_reports=4, day=1, time="06:00"),
    )
    monkeypatch.setattr(scan, "LokiClient", DummyLokiClient)
    result = scan.run_scan(settings, report_date="2026-08-17")
    assert result.status == "ok"
    traefik = next(container for container in result.report["containers"] if container["name"] == "traefik")
    assert traefik["error_groups"][0]["occurrences"] == 2


class DummyFailingClient:
    def __init__(self, *args, **kwargs):
        pass

    def query_range(self, query, start_ns, end_ns):
        raise ConnectionError("loki unreachable")


def test_scan_marks_loki_unavailable_when_first_page_fails(monkeypatch, tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (tmp_path / "data").mkdir()
    settings = SimpleNamespace(
        data_dir=tmp_path / "data",
        config_dir=config_dir,
        loki=SimpleNamespace(base_url="http://loki:3100", query_timeout_seconds=1, query_limit=1000, job_label="docker"),
        scan=SimpleNamespace(lookback="7d", timezone="UTC", max_log_lines_per_container=2, max_examples_per_error=10, max_error_groups_per_container=5, retention_reports=4, day=1, time="06:00"),
    )
    monkeypatch.setattr(scan, "LokiClient", DummyFailingClient)
    result = scan.run_scan(settings, report_date="2026-08-17")
    assert result.status == "error"
    assert result.report["state"] == "loki_unavailable"


class DummyPagingClientThenFailing:
    """First page succeeds and is big enough to force a second page (which
    fails) - simulates a client-side timeout partway through a multi-page
    scan, after some data was already fetched.
    """

    def __init__(self, *args, **kwargs):
        self.calls = 0

    def query_range(self, query, start_ns, end_ns):
        self.calls += 1
        if self.calls == 1:
            # Timestamps must fall inside the actual [start, end) scan window
            # (computed from real "now") so _next_page_start_ns advances the
            # cursor forward instead of seeing a page "behind" it and stopping.
            now = datetime.now(timezone.utc)
            return [
                SimpleNamespace(container="traefik", raw="error backend unavailable", timestamp=now - timedelta(minutes=5)),
                SimpleNamespace(container="traefik", raw="error backend unavailable", timestamp=now - timedelta(minutes=4)),
            ]
        raise TimeoutError("read timed out")


def test_scan_keeps_already_fetched_entries_when_later_page_times_out(monkeypatch, tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (tmp_path / "data").mkdir()
    settings = SimpleNamespace(
        data_dir=tmp_path / "data",
        config_dir=config_dir,
        loki=SimpleNamespace(base_url="http://loki:3100", query_timeout_seconds=1, query_limit=2, job_label="docker"),
        scan=SimpleNamespace(lookback="7d", timezone="UTC", max_log_lines_per_container=50, max_examples_per_error=10, max_error_groups_per_container=5, retention_reports=4, day=1, time="06:00"),
    )
    monkeypatch.setattr(scan, "LokiClient", DummyPagingClientThenFailing)
    result = scan.run_scan(settings, report_date="2026-08-17")
    assert result.status == "partial"
    assert result.report["state"] == "partial"
    assert "error" in result.report
    traefik = next(container for container in result.report["containers"] if container["name"] == "traefik")
    assert traefik["error_groups"][0]["occurrences"] == 2
