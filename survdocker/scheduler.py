from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, time, timezone
import time as time_module
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .scan import run_scan


@dataclass(frozen=True)
class SchedulePlan:
    next_run_utc: datetime
    next_run_local: datetime


def compute_next_run(now: datetime, day: int, schedule_time: str, timezone_name: str) -> SchedulePlan:
    try:
        tz = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        tz = timezone.utc
    localized_now = now.astimezone(tz)
    hour, minute = (int(part) for part in schedule_time.split(":", 1))
    candidate = localized_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    target_weekday = (day - 1) % 7
    days_ahead = (target_weekday - candidate.weekday()) % 7
    if days_ahead == 0 and candidate <= localized_now:
        days_ahead = 7
    candidate = candidate + timedelta(days=days_ahead)
    return SchedulePlan(next_run_utc=candidate.astimezone(timezone.utc), next_run_local=candidate)


def scheduler_loop(settings, stop_callback=None) -> None:
    while True:
        now = datetime.now(timezone.utc)
        plan = compute_next_run(now, settings.scan.day, settings.scan.time, settings.scan.timezone)
        wait_seconds = max(0.0, (plan.next_run_utc - now).total_seconds())
        if wait_seconds:
            time_module.sleep(min(wait_seconds, 60.0))
            continue
        run_scan(settings)
        if stop_callback and stop_callback():
            return
