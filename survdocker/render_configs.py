"""Renders configuration files from survdocker.yml template."""

from pathlib import Path
import yaml


def render_alloy_config(config_path: str | Path, output_dir: str = "survdocker/data") -> str:
    """
    Generate a valid Grafana Alloy configuration from survdocker.yml.
    
    The generated config includes:
    - loki.source.docker with targets and forward_to
    - loki.process with forward_to
    - loki.write with proper endpoint
    """
    # Convert to string if it's a Path object
    config_path_str = str(config_path)
    
    with open(config_path_str, 'r') as f:
        config = yaml.safe_load(f)
    
    # Ensure output directory exists
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Build Alloy config with proper syntax
    alloy_config = """// Generated from survdocker.yml
// Reads Docker logs through the local socket and pushes them to Loki.
// Loki endpoint: http://loki:3100/loki/api/v1/push

discovery.docker "containers" {
  host = "unix:///var/run/docker.sock"
}

discovery.relabel "containers" {
  targets = discovery.docker.containers.targets

  rule {
    source_labels = ["__meta_docker_container_name"]
    regex         = "/?(.*)"
    target_label  = "container"
  }
}

loki.source.docker "containers" {
  host          = "unix:///var/run/docker.sock"
  targets       = discovery.docker.containers.targets
  relabel_rules = discovery.relabel.containers.rules
  labels        = {"job" = "docker"}
  forward_to    = [loki.process.docker_logs.receiver]
}

loki.process "docker_logs" {
  // Drop orphan lines ingested before discovery.docker has resolved a
  // container's name (e.g. during Alloy's own startup) - these carry no
  // "container" label and would otherwise surface as a fake "docker" container.
  stage.match {
    selector = "{container=\\"\\"}"
    stage.drop {
      expression = ".*"
    }
  }

  forward_to = [loki.write.default.receiver]
}

loki.write "default" {
  endpoint {
    url = "http://loki:3100/loki/api/v1/push"
  }
}
"""
    
    # Write the config file (docker-compose mounts this as alloy.alloy)
    alloy_file = output_path / "alloy.alloy"
    with open(alloy_file, 'w') as f:
        f.write(alloy_config)
    
    return str(alloy_file)


def render_loki_config(settings, output_dir: str = "survdocker/system") -> str:
    """Generate the Loki server configuration from central settings."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    retention_hours = int(settings.loki.retention_days) * 24
    loki_config = f"""# Generated from survdocker.yml
# Loki query limit: {settings.loki.query_limit}
# Retention: {settings.loki.retention_days} day(s)
auth_enabled: false

analytics:
  reporting_enabled: false

server:
  http_listen_port: 3100
  grpc_server_max_recv_msg_size: 67108864
  grpc_server_max_send_msg_size: 67108864

common:
  path_prefix: /loki
  storage:
    filesystem:
      chunks_directory: /loki/chunks
      rules_directory: /loki/rules
  replication_factor: 1
  ring:
    kvstore:
      store: inmemory

schema_config:
  configs:
    - from: 2024-01-01
      store: tsdb
      object_store: filesystem
      schema: v13
      index:
        prefix: index_
        period: 24h

limits_config:
  retention_period: {retention_hours}h
  reject_old_samples_max_age: {retention_hours}h
  max_query_length: 0
  max_streams_per_user: 0
  max_entries_limit_per_query: {settings.loki.query_limit}

query_range:
  results_cache:
    cache:
      embedded_cache:
        enabled: true
"""

    loki_file = output_path / "loki-config.yml"
    with open(loki_file, "w") as f:
        f.write(loki_config)

    return str(loki_file)


def render_all_configs(settings) -> dict:
    """Render all configuration files from the main config."""
    results = {}

    # Both configs must land in runtime_config_dir (survdocker/system), which is what
    # docker-compose actually mounts into the loki/alloy containers.
    output_dir = str(getattr(settings, "runtime_config_dir", None) or Path("survdocker/system"))

    alloy_path = render_alloy_config(settings.config_file, output_dir=output_dir)
    results["alloy"] = alloy_path

    loki_path = render_loki_config(settings, output_dir=output_dir)
    results["loki"] = loki_path

    return results


if __name__ == "__main__":
    rendered = render_all_configs()
    print(f"Rendered configs: {rendered}")
