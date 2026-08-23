"""Docker healthcheck helper for long-running loops with no HTTP endpoint (scheduler, critical-monitor).

Usage: python -m survdocker.heartbeat_check <path-to-heartbeat.json> <max_age_seconds>

Exits 0 if the file's "timestamp" field is within max_age_seconds of now, 1 otherwise.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone


def main(argv: list[str]) -> int:
    path, max_age_seconds = argv[1], float(argv[2])
    try:
        with open(path) as handle:
            data = json.load(handle)
        timestamp = datetime.fromisoformat(data["timestamp"])
        age = (datetime.now(timezone.utc) - timestamp).total_seconds()
    except Exception:
        return 1
    return 0 if age <= max_age_seconds else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
