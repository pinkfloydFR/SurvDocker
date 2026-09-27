from datetime import datetime, timedelta, timezone

from survdocker.scheduler import compute_next_run


def test_monday_schedule_same_day_when_time_has_not_passed():
    now = datetime(2026, 8, 17, 5, 0, tzinfo=timezone.utc)
    plan = compute_next_run(now, day=1, schedule_time="06:00", timezone_name="UTC")
    assert plan.next_run_local.weekday() == 0
    assert plan.next_run_local.hour == 6
    assert plan.next_run_local.day == 17


def test_monday_schedule_advances_one_week_after_time_passed():
    now = datetime(2026, 8, 17, 7, 0, tzinfo=timezone.utc)
    plan = compute_next_run(now, day=1, schedule_time="06:00", timezone_name="UTC")
    assert plan.next_run_local.weekday() == 0
    assert plan.next_run_local.day == 24


def test_scheduler_loop_runs_scan_when_scheduled_time_is_reached(monkeypatch, tmp_path):
    from types import SimpleNamespace

    from survdocker import scheduler

    clock = [datetime(2026, 8, 17, 5, 59, 30, tzinfo=timezone.utc)]

    class FakeDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock[0]

    def fake_sleep(seconds):
        # Wake up slightly after the requested delay, as time.sleep does.
        clock[0] = clock[0] + timedelta(seconds=seconds, milliseconds=3)

    scans = []
    monkeypatch.setattr(scheduler, "datetime", FakeDatetime)
    monkeypatch.setattr(scheduler.time_module, "sleep", fake_sleep)
    monkeypatch.setattr(scheduler, "run_scan", lambda settings: scans.append(clock[0]))
    settings = SimpleNamespace(data_dir=tmp_path, scan=SimpleNamespace(day=1, time="06:00", timezone="UTC"))

    scheduler.scheduler_loop(settings, stop_callback=lambda: True)

    assert len(scans) == 1
    assert scans[0] - datetime(2026, 8, 17, 6, 0, tzinfo=timezone.utc) < timedelta(seconds=1)
