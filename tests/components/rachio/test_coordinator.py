"""Tests for the Rachio polling usage calculations."""

import pytest

from homeassistant.components.rachio.coordinator import (
    controller_calls_per_day,
    hose_timer_calls_per_day,
    min_poll_interval,
)


@pytest.mark.parametrize(
    ("controllers", "bases", "limit", "expected"),
    [
        pytest.param(1, 0, 3500, 0.5, id="one-controller"),
        pytest.param(2, 0, 3500, 1.0, id="two-controllers"),
        pytest.param(3, 0, 3500, 1.5, id="three-controllers"),
        pytest.param(1, 0, 3000, 1.0, id="headroom-for-other-calls"),
        pytest.param(1, 0, 1700, 1.0, id="smaller-limit"),
        pytest.param(1, 5, 3500, 1.0, id="hose-timers-use-budget"),
        pytest.param(131, 0, 3500, 60, id="longest-interval"),
        pytest.param(132, 0, 3500, None, id="no-interval-fits"),
    ],
)
def test_min_poll_interval(
    controllers: int, bases: int, limit: int, expected: float | None
) -> None:
    """Test the shortest allowed polling interval stays within the limit."""
    assert min_poll_interval(controllers, bases, limit) == expected


@pytest.mark.parametrize(
    ("controllers", "interval", "expected"),
    [(1, 0.5, 2880), (1, 1, 1440), (2, 1, 2880), (3, 5, 864)],
)
def test_controller_calls_per_day(
    controllers: int, interval: float, expected: int
) -> None:
    """Test the daily API calls used by polling controllers."""
    assert controller_calls_per_day(controllers, interval) == expected


@pytest.mark.parametrize(
    ("bases", "expected"), [(0, 0), (1, 768), (2, 1056), (5, 1440)]
)
def test_hose_timer_calls_per_day(bases: int, expected: int) -> None:
    """Test the daily API calls used by the smart hose timer coordinators."""
    assert hose_timer_calls_per_day(bases) == expected
