"""Tests for Habitica utility functions."""

import datetime
from typing import Any

import pytest

from homeassistant.components.habitica.util import next_due_date, to_date
from homeassistant.core import HomeAssistant


@pytest.fixture(autouse=True)
async def set_tz(hass: HomeAssistant) -> None:
    """Fixture to set timezone."""
    await hass.config.async_set_time_zone("Europe/Berlin")


@pytest.mark.parametrize(
    ("task", "calculated_due_date"),
    [
        (
            {
                "isDue": True,
                "completed": False,
                "frequency": "daily",
                "daysOfMonth": [],
                "startDate": "2024-07-06T22:00:00.000Z",
                "nextDue": [
                    "2024-09-22T22:00:00.000Z",
                    "2024-09-23T22:00:00.000Z",
                ],
            },
            (2024, 9, 23),
        ),
        (
            {
                "isDue": False,
                "completed": False,
                "frequency": "daily",
                "daysOfMonth": [],
                "startDate": "2024-09-23T22:00:00.000Z",
                "nextDue": [
                    "2024-09-22T22:00:00.000Z",
                    "2024-09-23T22:00:00.000Z",
                ],
            },
            (2024, 9, 24),
        ),
        (
            {
                "isDue": False,
                "completed": False,
                "frequency": "monthly",
                "daysOfMonth": [23],
                "startDate": "2024-10-22T22:00:00.000Z",
                "nextDue": [
                    "2024-10-22T22:00:00.000Z",
                    "2024-11-22T22:00:00.000Z",
                ],
            },
            (2024, 10, 23),
        ),
        (
            {
                "isDue": False,
                "completed": False,
                "frequency": "yearly",
                "daysOfMonth": [22],
                "startDate": "2024-10-22T22:00:00.000Z",
                "nextDue": [
                    "2024-10-22T22:00:00.000Z",
                    "2025-10-22T22:00:00.000Z",
                ],
            },
            (2024, 10, 23),
        ),
        (
            {
                "isDue": False,
                "completed": False,
                "frequency": "weekly",
                "daysOfMonth": [],
                "startDate": "2024-09-25T22:00:00.000Z",
                "nextDue": [
                    "2024-09-20T22:00:00.000Z",
                    "2024-09-27T22:00:00.000Z",
                ],
            },
            (2024, 9, 28),
        ),
        (
            {
                "isDue": False,
                "completed": False,
                "frequency": "monthly",
                "daysOfMonth": [],
                "startDate": "2024-09-25T22:00:00.000Z",
                "nextDue": [
                    "2024-09-20T22:00:00.000Z",
                    "2024-10-20T22:00:00.000Z",
                ],
            },
            (2024, 10, 21),
        ),
    ],
    ids=[
        "default",
        "daily starts on startdate",
        "monthly starts on startdate",
        "yearly starts on startdate",
        "weekly",
        "monthly starts on fixed day",
    ],
)
async def test_next_due_date(
    task: dict[str, Any],
    calculated_due_date: tuple,
) -> None:
    """Test next_due_date function."""

    result = next_due_date(task, "2024-09-22T22:01:55.586Z")
    assert result == datetime.datetime(*calculated_due_date).date()


@pytest.mark.parametrize(
    ("date", "expected_date"),
    [
        ("2024-09-22T22:00:00.000Z", datetime.datetime(2024, 9, 23).date()),
        ("Mon Sep 23 2024 00:00:00 GMT+0200", datetime.datetime(2024, 9, 23).date()),
        ("Mon Sep 23", None),
    ],
    ids=["iso datetime", "javascript datetime string", "malformed date"],
)
async def test_date_conversion(date: str, expected_date: datetime.date | None) -> None:
    """Test to_date function."""

    result = to_date(date)
    assert result == expected_date
