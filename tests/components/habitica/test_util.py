"""Tests for Habitica utility functions."""

import pytest

from homeassistant.components.habitica.util import get_recurrence_rule
from homeassistant.core import HomeAssistant


@pytest.fixture(autouse=True)
async def set_tz(hass: HomeAssistant) -> None:
    """Fixture to set timezone."""
    await hass.config.async_set_time_zone("Europe/Berlin")


async def test_get_recurrence_rule() -> None:
    """Test next_due_date function."""

    task = {
        "frequency": "weekly",
        "everyX": 1,
        "repeat": {
            "m": True,
            "t": False,
            "w": True,
            "f": False,
            "s": True,
            "su": False,
        },
        "type": "daily",
        "startDate": "2024-07-06T22:00:00.000Z",
        "daysOfMonth": [],
        "weeksOfMonth": [],
    }

    result = get_recurrence_rule(task)
    assert result == "FREQ=WEEKLY;BYDAY=MO,WE,SA"
