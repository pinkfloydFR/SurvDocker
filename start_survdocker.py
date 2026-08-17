from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from survdocker.config import load_settings
from survdocker.render_configs import render_all_configs


def run_command(command: list[str]) -> int:
    completed = subprocess.run(command, check=False)
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate SurvDocker configs and start the Compose stack.")
    parser.add_argument("--no-build", action="store_true", help="Start the stack without rebuilding images.")
    parser.add_argument("--detach", action="store_true", default=True, help="Run Compose in detached mode.")
    parser.add_argument("--no-detach", dest="detach", action="store_false", help="Run Compose in the foreground.")
    args = parser.parse_args()

    settings = load_settings()
    render_all_configs(settings)

    compose_file = Path.cwd() / "docker-compose.yml"
    command = ["docker", "compose", "-f", str(compose_file), "up"]
    if args.detach:
        command.append("-d")
    if not args.no_build:
        command.append("--build")

    return run_command(command)


if __name__ == "__main__":
    raise SystemExit(main())
