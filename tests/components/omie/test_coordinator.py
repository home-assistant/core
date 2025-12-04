"""Test the OMIE coordinator."""

import datetime as dt

import pytest

from homeassistant.components.omie.coordinator import calc_update_interval


@pytest.mark.parametrize(
    ("now_str", "expected_refresh_str"),
    [
        ("2025-11-11T10:17:32.153544", "2025-11-11T10:30:01.000000"),
        ("2025-11-11T13:07:32.134523", "2025-11-11T13:15:01.000000"),
        ("2025-11-11T18:32:57.346478", "2025-11-11T18:45:01.000000"),
        ("2025-11-11T23:49:34.879681", "2025-11-12T00:00:01.000000"),
    ],
)
def test_calc_update_interval(now_str: str, expected_refresh_str) -> None:
    """Refresh should happen at every 15-minute boundary +1 second to avoid early trigger.

    Early triggering is caused by loss of the decimal part of loop.time() when the
    coordinator schedules the refresh.
    """
    now = dt.datetime.fromisoformat(now_str)
    update_interval = calc_update_interval(now)

    assert now + update_interval == dt.datetime.fromisoformat(expected_refresh_str)
