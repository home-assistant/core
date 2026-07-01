"""Test the HomeKit climate helper functions."""

import pytest

from homeassistant.components.homekit.climate_util import (
    HEAT_COOL_DEADBAND,
    resolve_target_temp_range,
)


@pytest.mark.parametrize(
    ("current_high", "current_low", "new_high", "new_low", "expected"),
    [
        # Ordered pair within bounds is returned unchanged.
        (24.0, 20.0, 25.0, None, (25.0, 20.0)),
        (24.0, 20.0, None, 21.0, (24.0, 21.0)),
        # A narrow but ordered band is preserved; the deadband is not forced.
        (24.0, 20.0, None, 23.0, (24.0, 23.0)),
        # New high crossing below the low enforces the deadband.
        (24.0, 20.0, 18.0, None, (18.0, 18.0 - HEAT_COOL_DEADBAND)),
        # New low crossing above the high enforces the deadband.
        (20.0, 16.0, None, 22.0, (22.0 + HEAT_COOL_DEADBAND, 22.0)),
        # Low dragged to the max: the deadband survives the clamp by moving high.
        (20.0, 18.0, None, 30.0, (30.0, 30.0 - HEAT_COOL_DEADBAND)),
        # High dragged to the min: the deadband survives by moving high up.
        (24.0, 20.0, 7.0, None, (7.0 + HEAT_COOL_DEADBAND, 7.0)),
    ],
)
def test_resolve_target_temp_range(
    current_high: float,
    current_low: float,
    new_high: float | None,
    new_low: float | None,
    expected: tuple[float, float],
) -> None:
    """Test the range resolver keeps an ordered, in-bounds pair with a deadband."""
    assert (
        resolve_target_temp_range(
            current_high, current_low, new_high, new_low, 7.0, 30.0
        )
        == expected
    )
