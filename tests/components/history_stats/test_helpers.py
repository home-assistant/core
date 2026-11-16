"""Test the History stats helpers."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from homeassistant.components.history_stats.helpers import pretty_ratio
from homeassistant.core import HomeAssistant

# Falls back on 2026-11-01 and springs forward on 2026-03-08
TIME_ZONE = "US/Pacific"


@pytest.mark.parametrize(
    ("value", "start", "end", "expected"),
    [
        pytest.param(
            90000,
            datetime(2026, 11, 1),
            datetime(2026, 11, 2),
            100.0,
            id="naive_bounds_over_fall_back",
        ),
        pytest.param(
            90000,
            datetime(2026, 11, 1, tzinfo=ZoneInfo(TIME_ZONE)),
            datetime(2026, 11, 2, tzinfo=ZoneInfo(TIME_ZONE)),
            100.0,
            id="local_bounds_over_fall_back",
        ),
        pytest.param(
            82800,
            datetime(2026, 3, 8, tzinfo=ZoneInfo(TIME_ZONE)),
            datetime(2026, 3, 9, tzinfo=ZoneInfo(TIME_ZONE)),
            100.0,
            id="local_bounds_over_spring_forward",
        ),
        pytest.param(
            0,
            datetime(2026, 3, 8, 2, 30, tzinfo=ZoneInfo(TIME_ZONE)),
            datetime(2026, 3, 8, 3, 30, tzinfo=ZoneInfo(TIME_ZONE)),
            0.0,
            id="skipped_hour_has_no_length",
        ),
    ],
)
async def test_pretty_ratio(
    hass: HomeAssistant,
    value: float,
    start: datetime,
    end: datetime,
    expected: float,
) -> None:
    """Test the ratio uses the real length of the period."""
    # Naive bounds are in the time zone of Home Assistant, not of the host
    await hass.config.async_set_time_zone(TIME_ZONE)

    assert pretty_ratio(value, (start, end)) == expected
