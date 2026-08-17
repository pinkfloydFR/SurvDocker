from __future__ import annotations

import argparse

from .config import load_settings
from .monitor import run_critical_monitor
from .render_configs import render_all_configs
from .scan import run_scan
from .scheduler import scheduler_loop
from .web import create_app


def main() -> None:
    parser = argparse.ArgumentParser(prog="survdocker")
    parser.add_argument("command", choices={"web", "scan-once", "scheduler", "critical-monitor", "render-configs"})
    args = parser.parse_args()
    settings = load_settings()
    if args.command == "web":
        app = create_app()
        app.run(host=settings.host, port=settings.port)
    elif args.command == "scan-once":
        run_scan(settings)
    elif args.command == "scheduler":
        scheduler_loop(settings)
    elif args.command == "critical-monitor":
        run_critical_monitor(settings, {}, settings.data_dir / "critical-state.json")
    elif args.command == "render-configs":
        paths = render_all_configs(settings)
        for name, path in paths.items():
            print(f"generated {name}: {path}")


if __name__ == "__main__":
    main()
