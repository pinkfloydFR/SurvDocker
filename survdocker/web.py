from __future__ import annotations

from datetime import datetime
from pathlib import Path
from threading import Thread

from flask import Flask, abort, jsonify, render_template, request, send_file

from .analyzer import format_report_copy, report_summary
from .config import load_settings
from .scan import run_scan
from .storage import latest_report_path, list_reports, load_report


def create_app() -> Flask:
    settings = load_settings()
    app = Flask(__name__, template_folder=str(Path(__file__).with_name("templates")))
    app.config["SURVDOCKER_SETTINGS"] = settings

    @app.get("/health")
    def health() -> tuple[dict, int]:
        report = load_report(latest_report_path(settings.data_dir))
        scan_state = load_report(settings.data_dir / "last-scan.json") or {}
        return jsonify({
            "status": "ok",
            "report_exists": report is not None,
            "scan_state": scan_state.get("status", "unknown"),
            "telegram_enabled": settings.telegram.enabled,
        }), 200

    @app.get("/")
    def index():
        report = load_report(latest_report_path(settings.data_dir))
        summary = report_summary(report) if report else None
        return render_template(
            "index.html",
            report=report,
            summary=summary,
            reports=list_reports(settings.data_dir),
            settings=settings,
            format_report_copy=format_report_copy,
        )

    @app.get("/reports")
    def reports():
        available = []
        for path in list_reports(settings.data_dir):
            payload = load_report(path) or {}
            available.append({"path": path.name, "report": payload, "summary": report_summary(payload)})
        return render_template("reports.html", reports=available)

    @app.get("/reports/<report_name>")
    def report_detail(report_name: str):
        path = settings.data_dir / "reports" / f"{report_name}.json"
        report = load_report(path)
        if report is None:
            abort(404)
        return render_template("report_detail.html", report=report, report_name=report_name, summary=report_summary(report))

    @app.get("/reports/<report_name>.json")
    def report_json(report_name: str):
        path = settings.data_dir / "reports" / f"{report_name}.json"
        if not path.exists():
            abort(404)
        return send_file(path, mimetype="application/json", as_attachment=True, download_name=f"{report_name}.json")

    @app.get("/reports/<report_name>.txt")
    def report_text(report_name: str):
        path = settings.data_dir / "reports" / f"{report_name}.json"
        report = load_report(path)
        if report is None:
            abort(404)
        lines = [f"SurvDocker report {report_name}"]
        for container in report.get("containers", []):
            lines.append(f"\n[{container['name']}]")
            for group in container.get("error_groups", []):
                lines.append(format_report_copy(group, report))
                lines.append("")
        return "\n".join(lines), 200, {"Content-Type": "text/plain; charset=utf-8"}

    @app.post("/scan-now")
    def scan_now():
        if request.headers.get("X-SurvDocker-Token") != settings.scan_token:
            abort(403)

        def _run_scan() -> None:
            run_scan(settings)

        Thread(target=_run_scan, daemon=True).start()
        return jsonify({"status": "accepted", "message": "scan request queued"}), 202

    return app


def main() -> None:
    settings = load_settings()
    app = create_app()
    app.run(host=settings.host, port=settings.port, debug=False)


if __name__ == "__main__":
    main()
