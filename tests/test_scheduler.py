from datetime import datetime, timezone

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
