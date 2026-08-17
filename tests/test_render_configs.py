from pathlib import Path
from types import SimpleNamespace

from survdocker.render_configs import render_all_configs, render_alloy_config, render_loki_config


def test_render_loki_config_contains_central_values():
    settings = SimpleNamespace(
        loki=SimpleNamespace(base_url="http://loki:3100", query_limit=1234, job_label="docker", retention_days=30),
        scan=SimpleNamespace(retention_reports=4),
    )
    text = render_loki_config(settings)
    assert "retention_period: 720h" in text
    assert "max_streams_per_user: 0" in text


def test_render_alloy_config_contains_central_values():
    settings = SimpleNamespace(
        loki=SimpleNamespace(base_url="http://loki:3100", job_label="docker", retention_days=30),
        scan=SimpleNamespace(retention_reports=4),
    )
    text = render_alloy_config(settings)
    assert 'job = "docker"' in text
    assert 'url = "http://loki:3100/loki/api/v1/push"' in text


def test_render_all_configs_writes_files(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    settings = SimpleNamespace(
        config_dir=config_dir,
        loki=SimpleNamespace(base_url="http://loki:3100", query_limit=1234, job_label="docker", retention_days=30),
        scan=SimpleNamespace(retention_reports=4),
    )
    paths = render_all_configs(settings)
    assert paths["loki"].exists()
    assert paths["alloy"].exists()
