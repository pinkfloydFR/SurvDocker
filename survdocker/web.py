from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import Thread

from flask import Flask, Response, abort, jsonify, render_template, request, send_file

from .analyzer import format_report_copy, report_summary
from .config import load_settings
from .loki import LokiClient
from .scan import compute_period, run_scan
from .storage import latest_report_path, list_reports, load_report
from .telegram import send_message


def _format_datetime(value: str | None) -> str:
    if not value:
        return "-"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return value
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


def create_app() -> Flask:
    settings = load_settings()
    app = Flask(__name__, template_folder=str(Path(__file__).with_name("templates")))
    app.config["SURVDOCKER_SETTINGS"] = settings
    app.jinja_env.filters["format_datetime"] = _format_datetime

    @app.get("/health")
    def health() -> tuple[dict, int]:
        report = load_report(latest_report_path(settings.data_dir))
        scan_state = load_report(settings.data_dir / "last-scan.json") or {}
        return jsonify({
            "status": "ok",
            "report_exists": report is not None,
            "scan_state": scan_state.get("status", "unknown"),
            "scan_timestamp": scan_state.get("timestamp"),
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

    @app.get("/containers/<container_name>/logs")
    def container_logs(container_name: str):
        start_param = request.args.get("start")
        end_param = request.args.get("end")
        start = end = None
        if start_param and end_param:
            try:
                start = datetime.fromisoformat(start_param)
                end = datetime.fromisoformat(end_param)
            except ValueError:
                start = end = None
        if start is None or end is None:
            start, end = compute_period(datetime.now(timezone.utc), settings.scan.lookback, settings.scan.timezone)

        escaped_name = container_name.replace("\\", "\\\\").replace('"', '\\"')
        query = f'{{job="{settings.loki.job_label}", container="{escaped_name}"}}'
        client = LokiClient(settings.loki.base_url, timeout_seconds=settings.loki.query_timeout_seconds, query_limit=settings.loki.query_limit)
        try:
            entries = client.query_range(query, int(start.timestamp() * 1_000_000_000), int(end.timestamp() * 1_000_000_000))
        except Exception as exc:
            return Response(f"Impossible de récupérer les logs depuis Loki: {exc}", status=502, mimetype="text/plain")

        entries.sort(key=lambda entry: entry.timestamp or datetime.min.replace(tzinfo=timezone.utc))
        lines = [f"{entry.timestamp.isoformat() if entry.timestamp else '?'}  {entry.raw}" for entry in entries]
        body = "\n".join(lines) if lines else f"(aucune ligne pour {container_name} sur cette période)"
        return Response(body, mimetype="text/plain")

    @app.post("/test-alert")
    def test_alert():
        if request.headers.get("X-SurvDocker-Token") != settings.scan_token:
            abort(403)
        if not settings.telegram.enabled or not settings.telegram.bot_token or not settings.telegram.chat_id:
            return jsonify({"ok": False, "message": "Telegram non configuré (TELEGRAM_ENABLED/BOT_TOKEN/CHAT_ID)."}), 400

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        text = f"🔔 Test d'alerte SurvDocker — {now} UTC. Si tu reçois ce message, les alertes Telegram fonctionnent."
        result = send_message(settings.telegram.api_base_url, settings.telegram.bot_token, settings.telegram.chat_id, text, settings.telegram.thread_id)
        return jsonify({"ok": result.ok, "status_code": result.status_code, "message": result.message}), (200 if result.ok else 502)

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
