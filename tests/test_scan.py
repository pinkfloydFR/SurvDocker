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
