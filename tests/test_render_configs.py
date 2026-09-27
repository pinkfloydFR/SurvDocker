from pathlib import Path
from types import SimpleNamespace

from survdocker.render_configs import render_all_configs, render_alloy_config, render_loki_config

# Every test writes into tmp_path: the render functions default to the real
# survdocker/system directory, which is mounted into the running loki/alloy
# containers, so a test must never rely on those defaults.

CONFIG_FILE = Path("survdocker/config/survdocker.yml")


def _settings(tmp_path):
    return SimpleNamespace(
        config_file=CONFIG_FILE,
        runtime_config_dir=tmp_path / "system",
        loki=SimpleNamespace(base_url="http://loki:3100", query_limit=1234, job_label="docker", retention_days=30),
        scan=SimpleNamespace(retention_reports=4),
    )


def test_render_loki_config_contains_central_values(tmp_path):
    path = render_loki_config(_settings(tmp_path), output_dir=str(tmp_path))
    text = Path(path).read_text()
    assert "retention_period: 720h" in text
    assert "max_streams_per_user: 0" in text
    assert "max_entries_limit_per_query: 1234" in text


def test_render_alloy_config_contains_central_values(tmp_path):
    path = render_alloy_config(CONFIG_FILE, output_dir=str(tmp_path))
    text = Path(path).read_text()
    assert '"job" = "docker"' in text
    assert 'url = "http://loki:3100/loki/api/v1/push"' in text


def test_render_all_configs_writes_into_runtime_config_dir(tmp_path):
    settings = _settings(tmp_path)
    paths = render_all_configs(settings)
    assert Path(paths["loki"]).parent == settings.runtime_config_dir
    assert Path(paths["alloy"]).parent == settings.runtime_config_dir
    assert Path(paths["loki"]).exists()
    assert Path(paths["alloy"]).exists()
