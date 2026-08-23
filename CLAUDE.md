# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

SurvDocker is under active development — the README explicitly warns `EN COURS DE DEVELOPPEMENT, NE PAS DEPLOYER` (in development, do not deploy). It is a local Flask app that analyzes Docker logs shipped through Grafana Alloy into Loki, produces a weekly persisted report, and shows the latest report behind Traefik + Authelia.

## Commands

```bash
pip install -r requirements.txt   # Flask, PyYAML, requests, pytest
pytest -q                         # run the full test suite (this is the only locally-verifiable path)
pytest tests/test_scan.py -q      # run a single test file
pytest tests/test_scan.py::test_scan_respects_per_container_limit -q  # run a single test

python -m survdocker web               # run the Flask app directly (host/port from settings)
python -m survdocker scan-once         # run one scan against Loki and persist a report
python -m survdocker scheduler         # blocking loop that triggers scan-once on the configured weekly schedule
python -m survdocker critical-monitor  # one-shot poll of the Docker API for critical container state, sends Telegram alerts
python -m survdocker render-configs    # regenerate survdocker/system/{loki-config.yml,alloy.alloy} from survdocker.yml

python start_survdocker.py             # render configs, then `docker compose up -d --build` for the full stack
```

There is no real Docker/Loki integration available in the dev environment — only the Python logic is unit-testable locally (see README "Validation locale").

## Architecture

**Settings are the spine of the app.** `survdocker/config.py:load_settings()` reads `survdocker/config/survdocker.yml` (business/scan/filter config) and layers environment variables on top for anything infrastructure-related (hosts, ports, Loki URL, Traefik middleware chain, Telegram secrets — env vars always win). The resulting frozen `Settings` dataclass is passed explicitly into every other module; there is no global state. This is the file to read first when tracing how a value flows from config to behavior.

**Two config domains, deliberately separated:**
- `survdocker/config/survdocker.yml` — user-edited business config (scan schedule/lookback, log filters, critical-monitor thresholds/dependencies). Not meant to contain infra values.
- `survdocker/system/loki-config.yml` and `survdocker/system/alloy.alloy` — machine-generated technical configs, produced by `survdocker/render_configs.py` from the central YAML + settings, and mounted read-only into the `loki`/`alloy` containers. Regenerate with `python -m survdocker render-configs` after changing anything that affects them; never hand-edit them.

Infra values (Traefik host/middleware chain, `LOKI_BASE_URL`, Telegram secrets, container-visible directories) live in `.env` / `docker-compose.yml`, not in `survdocker.yml` — see DEPLOYMENT.md.

**Scan pipeline** (`scan.py` orchestrates; each stage is independently testable):
1. `loki.py` `LokiClient.query_range` pulls raw log lines for the configured lookback window from Loki's HTTP API.
2. `filters.py` decides per-line keep/ignore via regex `ignore_patterns`/`keep_patterns`/`warning_patterns` (defaults + user overrides from settings) and classifies a level (`fatal`/`error`/`warning`/`unknown`).
3. `normalize.py` strips volatile substrings (UUIDs, timestamps, IPs, ports, hex IDs, paths) from a message so recurring errors collapse to one pattern.
4. `analyzer.py` groups filtered/normalized entries into `ErrorGroup`s keyed by `(container, normalized_message)`, caps examples per group and groups per container, and builds the final report dict.
5. `storage.py` writes `data/reports/report-<date>.json`, updates `data/latest-report.json`, and prunes old reports beyond `scan.retention_reports`.

Loki being unreachable is a handled outcome, not an exception path to avoid: `run_scan` catches failures and persists a `state: "loki_unavailable"` report plus `last-scan.json`, so `/health` and the UI can reflect it instead of crashing.

**Critical monitor** (`monitor.py`) is a separate concern from the weekly scan: it talks to the Docker Engine API directly over the Unix socket (hand-rolled minimal HTTP client — `_connect_unix_http`, no docker SDK) to catch containers in `CRITICAL_STATES`, restart-loop spikes, or dependency-failure log patterns, and pushes Telegram alerts with a per-alert-key cooldown tracked in `data/critical-state.json`. It also sends a recovery message when a previously active alert key disappears. `run_critical_monitor` itself does one poll and returns — continuous polling comes from `critical_monitor_loop` (sleeps `CRITICAL_MONITOR_INTERVAL_SECONDS`, default 60s, between polls), which is what `__main__.py`'s `critical-monitor` subcommand actually calls. Don't call `run_critical_monitor` directly from a long-running entrypoint — without the loop wrapper the process exits immediately and the container just crash-loops under `restart: unless-stopped`. This runs as its own process/container (`survdocker-critical-monitor` in compose), independent of `web` and `scheduler`.

**Scheduler** (`scheduler.py`) is a simple blocking loop, not cron: `compute_next_run` figures out the next `scan.day`/`scan.time` occurrence in `scan.timezone`, sleeps in ≤60s increments, then calls `run_scan` directly. Runs as its own container so the weekly scan doesn't depend on someone hitting the web app.

**Web app** (`web.py`) is intentionally thin — it only reads what `scan.py`/`storage.py` already produced (`/`, `/reports`, `/reports/<name>[.json|.txt]`) plus `/health`, and `/scan-now` (token-guarded via `X-SurvDocker-Token` against `settings.scan_token`) just kicks a scan off on a background thread and returns 202 immediately rather than blocking the request.

**Process boundary:** `web`, `scheduler`, and `critical-monitor` are three separate Docker Compose services built from the same image (see `docker-compose.yml`), all driven by `survdocker/__main__.py`'s subcommand dispatch. They share `data/` (mounted volume) as their only communication channel — there's no IPC or shared process state, so report/alert state must go through `storage.py`'s JSON files.

## Known inconsistency

`render_configs.py` now generates working `alloy.alloy` and `loki-config.yml` into `settings.runtime_config_dir` (`survdocker/system`, matching what `docker-compose.yml` actually mounts into the `loki`/`alloy` containers), but `tests/test_render_configs.py` was written against an older, incompatible contract: it expects `render_alloy_config(settings)`/`render_loki_config(settings)` to take a `Settings` object and return generated text, and expects `render_all_configs` to write into `settings.config_dir` (the user-editable business-config directory) instead of `runtime_config_dir`. Writing generated system config into `config_dir` would be wrong in production (it's mounted read-only as user config), so the current code intentionally does not follow the test's contract — the test file itself needs updating, not the implementation. Confirmed by running the full stack locally (`docker compose up -d --build`) on 2026-08-23: with the corrected generation, `alloy` picks up real Docker container names via `discovery.docker` + `discovery.relabel` (source label `__meta_docker_container_name` → `container`), and Loki's `limits_config.max_entries_limit_per_query` now matches `loki.query_limit` (was previously missing, causing every scan to fail with a 400 from Loki once query volume exceeded Loki's 5000-entry default).
