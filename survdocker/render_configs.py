from __future__ import annotations

from pathlib import Path

from .config import Settings, generated_config_paths


def render_loki_config(settings: Settings) -> str:
    return "\n".join(
        [
            "# Generated from survdocker.yml",
            f"# Loki query limit: {settings.loki.query_limit}",
            f"# Retention: {settings.loki.retention_days} day(s)",
            "auth_enabled: false",
            "",
            "server:",
            "  http_listen_port: 3100",
            "",
            "common:",
            "  path_prefix: /loki",
            "  storage:",
            "    filesystem:",
            "      chunks_directory: /loki/chunks",
            "      rules_directory: /loki/rules",
            "  replication_factor: 1",
            "  ring:",
            "    kvstore:",
            "      store: inmemory",
            "",
            "schema_config:",
            "  configs:",
            "    - from: 2024-01-01",
            "      store: tsdb",
            "      object_store: filesystem",
            "      schema: v13",
            "      index:",
            "        prefix: index_",
            "        period: 24h",
            "",
            "limits_config:",
            f"  retention_period: {settings.loki.retention_days * 24}h",
            "  max_query_length: 0",
            "  max_streams_per_user: 0",
            "",
            "query_range:",
            "  results_cache:",
            "    cache:",
            "      embedded_cache:",
            "        enabled: true",
            "",
        ]
    )


def render_alloy_config(settings: Settings) -> str:
    return "\n".join(
        [
            "# Generated from survdocker.yml",
            "# Reads Docker logs through the local socket and pushes them to Loki.",
            f"# Loki endpoint: {settings.loki.base_url}/loki/api/v1/push",
            "loki.source.docker \"containers\" {",
            "  host = \"unix:///var/run/docker.sock\"",
            "}",
            "",
            "loki.process \"docker_logs\" {",
            "  stage.labels {",
            "    values = {",
            f"      job = \"{settings.loki.job_label}\",",
            "    }",
            "  }",
            "}",
            "",
            "loki.write \"default\" {",
            "  endpoint {",
            f"    url = \"{settings.loki.base_url.rstrip('/')}/loki/api/v1/push\"",
            "  }",
            "}",
            "",
        ]
    )


def render_all_configs(settings: Settings) -> dict[str, Path]:
    paths = generated_config_paths(settings)
    paths.loki_config_path.write_text(render_loki_config(settings), encoding="utf-8")
    paths.alloy_config_path.write_text(render_alloy_config(settings), encoding="utf-8")
    return {"loki": paths.loki_config_path, "alloy": paths.alloy_config_path}
