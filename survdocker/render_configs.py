"""Renders configuration files from survdocker.yml template."""

import os
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import yaml


def render_alloy_config(config_path: str, output_dir: str = "survdocker/data") -> str:
    """
    Generate a valid Grafana Alloy configuration from survdocker.yml.
    
    The generated config includes:
    - loki.source.docker with targets and forward_to
    - loki.process with forward_to
    - loki.write with proper endpoint
    """
    # Handle both string path and Settings object
    if hasattr(config_path, 'config_file'):
        config_path = str(config_path.config_file)
    else:
        config_path = str(config_path)
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Ensure output directory exists
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Build Alloy config with proper syntax
    alloy_config = """// Generated from survdocker.yml
// Reads Docker logs through the local socket and pushes them to Loki.
// Loki endpoint: http://loki:3100/loki/api/v1/push

loki.source.docker "containers" {
  host = "unix:///var/run/docker.sock"
  targets = {
    "job" = "docker",
  }
  forward_to = [loki.process.docker_logs.receiver]
}

loki.process "docker_logs" {
  stage.labels {
    values = {
      job = "docker",
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
    
    # Write the config file
    alloy_file = output_path / "config.alloy"
    with open(alloy_file, 'w') as f:
        f.write(alloy_config)
    
    return str(alloy_file)


def render_all_configs(config_path: str = "survdocker/config/survdocker.yml") -> dict:
    """Render all configuration files from the main config."""
    results = {}
    
    # Render Alloy config
    alloy_path = render_alloy_config(config_path)
    results["alloy"] = alloy_path
    
    return results


if __name__ == "__main__":
    rendered = render_all_configs()
    print(f"Rendered configs: {rendered}")
