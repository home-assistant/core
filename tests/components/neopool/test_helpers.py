"""Tests for the NeoPool helper functions."""

from datetime import UTC, timedelta

import pytest

from homeassistant.components.neopool.helpers import calculate_next_interval_time
from homeassistant.util import dt as dt_util


def test_calculate_next_interval_time_returns_utc_rounded_to_minute() -> None:
    """The next-interval timestamp is rounded to the nearest minute in UTC."""
    result = calculate_next_interval_time(7200)
    assert result is not None
    assert result.tzinfo == UTC
    assert result.second == 0
    assert result.microsecond == 0
    expected = (dt_util.utcnow() + timedelta(seconds=7200)).replace(
        second=0, microsecond=0
    )
    assert abs((result - expected).total_seconds()) < 60


@pytest.mark.parametrize("invalid", [0, -100, None])
def test_calculate_next_interval_time_invalid_input(invalid: float | None) -> None:
    """Zero, negative or None seconds yield None."""
    assert calculate_next_interval_time(invalid) is None
