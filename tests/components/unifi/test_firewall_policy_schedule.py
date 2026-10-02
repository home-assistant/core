"""Test building UniFi firewall policy schedules."""

from datetime import date, time
from typing import Any

from aiounifi.models.firewall_policy import FirewallPolicyScheduleMode
import pytest

from homeassistant.components.unifi.firewall_policy_schedule import (
    build_schedule,
    parse_date,
    parse_time,
    schedule_uses_times,
)

TODAY = date(2026, 1, 16)

EVERY_DAY = {
    "mode": "EVERY_DAY",
    "time_range_start": "21:00",
    "time_range_end": "08:00",
}
ONE_TIME = {
    "mode": "ONE_TIME_ONLY",
    "date": "2026-01-10",
    "time_range_start": "21:30",
    "time_range_end": "08:30",
}
WEEKLY = {
    "mode": "EVERY_WEEK",
    "repeat_on_days": ["wed", "mon"],
    "time_all_day": False,
    "time_range_start": "15:00",
    "time_range_end": "17:00",
}
WEEKLY_ALL_DAY = {"mode": "EVERY_WEEK", "repeat_on_days": ["fri"], "time_all_day": True}
CUSTOM = {
    "mode": "CUSTOM",
    "date_start": "2026-01-05",
    "date_end": "2026-01-30",
    "repeat_on_days": ["fri", "mon"],
    "time_all_day": False,
    "time_range_start": "20:00",
    "time_range_end": "06:00",
}


@pytest.mark.parametrize(
    ("current", "changes", "expected"),
    [
        # Mode changes build a clean schedule and keep the current times.
        (EVERY_DAY, {"mode": FirewallPolicyScheduleMode.ALWAYS}, {"mode": "ALWAYS"}),
        (
            EVERY_DAY,
            {"mode": FirewallPolicyScheduleMode.ONE_TIME_ONLY},
            {
                "mode": "ONE_TIME_ONLY",
                "date": "2026-01-16",
                "time_range_start": "21:00",
                "time_range_end": "08:00",
            },
        ),
        # One time keys don't leak into Every day.
        (
            ONE_TIME,
            {"mode": FirewallPolicyScheduleMode.EVERY_DAY},
            {
                "mode": "EVERY_DAY",
                "time_range_start": "21:30",
                "time_range_end": "08:30",
            },
        ),
        # Without times, the UniFi UI's defaults are used.
        (
            {"mode": "ALWAYS"},
            {"mode": FirewallPolicyScheduleMode.EVERY_DAY},
            {
                "mode": "EVERY_DAY",
                "time_range_start": "09:00",
                "time_range_end": "12:00",
            },
        ),
        # Switching to One time always dates it today, even from One time's
        # own stale date when the mode is re-selected from another mode.
        (
            WEEKLY_ALL_DAY,
            {"mode": FirewallPolicyScheduleMode.ONE_TIME_ONLY},
            {
                "mode": "ONE_TIME_ONLY",
                "date": "2026-01-16",
                "time_range_start": "09:00",
                "time_range_end": "12:00",
            },
        ),
        # Every week and Custom start with every day and today's dates.
        (
            EVERY_DAY,
            {"mode": FirewallPolicyScheduleMode.CUSTOM},
            {
                "mode": "CUSTOM",
                "date_start": "2026-01-16",
                "date_end": "2026-01-16",
                "repeat_on_days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
                "time_all_day": False,
                "time_range_start": "21:00",
                "time_range_end": "08:00",
            },
        ),
        # Value changes keep the mode and everything else it uses.
        (
            EVERY_DAY,
            {"start": time(22, 15, 45)},
            {
                "mode": "EVERY_DAY",
                "time_range_start": "22:15",
                "time_range_end": "08:00",
            },
        ),
        (
            ONE_TIME,
            {"start_date": date(2026, 2, 1)},
            {
                "mode": "ONE_TIME_ONLY",
                "date": "2026-02-01",
                "time_range_start": "21:30",
                "time_range_end": "08:30",
            },
        ),
        (
            ONE_TIME,
            {"end": time(7, 0)},
            {
                "mode": "ONE_TIME_ONLY",
                "date": "2026-01-10",
                "time_range_start": "21:30",
                "time_range_end": "07:00",
            },
        ),
        # Days are sent Monday first, whatever order the controller used.
        (
            WEEKLY,
            {"end": time(18, 0)},
            {
                "mode": "EVERY_WEEK",
                "repeat_on_days": ["mon", "wed"],
                "time_all_day": False,
                "time_range_start": "15:00",
                "time_range_end": "18:00",
            },
        ),
        (
            CUSTOM,
            {"end_date": date(2026, 2, 28)},
            {
                "mode": "CUSTOM",
                "date_start": "2026-01-05",
                "date_end": "2026-02-28",
                "repeat_on_days": ["mon", "fri"],
                "time_all_day": False,
                "time_range_start": "20:00",
                "time_range_end": "06:00",
            },
        ),
        # An all-day schedule has no times, and a stray date isn't carried.
        (
            {**WEEKLY_ALL_DAY, "date": "2026-01-01"},
            {},
            {"mode": "EVERY_WEEK", "repeat_on_days": ["fri"], "time_all_day": True},
        ),
    ],
)
def test_build_schedule(
    current: dict[str, Any], changes: dict[str, Any], expected: dict[str, Any]
) -> None:
    """A built schedule has exactly the keys its mode uses."""
    assert build_schedule(current, TODAY, **changes) == expected


@pytest.mark.parametrize(
    ("schedule", "expected"),
    [
        ({"mode": "ALWAYS"}, False),
        ({"mode": "SUNRISE"}, False),
        ({}, False),
        (EVERY_DAY, True),
        (ONE_TIME, True),
        (WEEKLY, True),
        (WEEKLY_ALL_DAY, False),
        # All day only counts in the modes that have it.
        ({**EVERY_DAY, "time_all_day": True}, True),
    ],
)
def test_schedule_uses_times(schedule: dict[str, Any], expected: bool) -> None:
    """Times apply unless the mode has none or the schedule is all day."""
    assert schedule_uses_times(schedule) is expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("21:30", time(21, 30)),
        ("00:00", time(0, 0)),
        ("25:00", None),
        ("9", None),
        (None, None),
        (2130, None),
    ],
)
def test_parse_time(value: object, expected: time | None) -> None:
    """Malformed times give None."""
    assert parse_time(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-01-16", date(2026, 1, 16)),
        ("2026-13-01", None),
        (None, None),
        (20260116, None),
    ],
)
def test_parse_date(value: object, expected: date | None) -> None:
    """Malformed dates give None."""
    assert parse_date(value) == expected
