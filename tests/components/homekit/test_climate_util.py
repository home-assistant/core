"""Test the HomeKit climate helper functions."""

import pytest

from homeassistant.components.climate import (
    ATTR_FAN_MODES,
    ATTR_MAX_TEMP,
    ATTR_MIN_TEMP,
    ATTR_SWING_MODES,
)
from homeassistant.components.homekit.climate_util import (
    HEAT_COOL_DEADBAND,
    get_fan_modes_and_speeds,
    get_swing_on_mode,
    get_temperature_range_from_state,
    resolve_target_temp_range,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import State


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


@pytest.mark.parametrize(
    ("attrs", "expected"),
    [
        # A reported bound of exactly 0 is honored, not treated as missing.
        ({ATTR_MIN_TEMP: 0, ATTR_MAX_TEMP: 25}, (0.0, 25.0)),
        # A missing minimum falls back to the default.
        ({ATTR_MAX_TEMP: 25}, (7.0, 25.0)),
        # A missing maximum falls back to the default.
        ({ATTR_MIN_TEMP: 10}, (10.0, 35.0)),
        # Both missing use both defaults.
        ({}, (7.0, 35.0)),
    ],
)
def test_get_temperature_range_from_state(
    attrs: dict[str, float], expected: tuple[float, float]
) -> None:
    """Test reported bounds are honored, including an explicit 0, else defaults."""
    state = State("climate.test", "cool", attrs)
    assert (
        get_temperature_range_from_state(state, UnitOfTemperature.CELSIUS, 7.0, 35.0)
        == expected
    )


def test_get_fan_modes_and_speeds_ignores_non_string() -> None:
    """Test non-string fan modes are ignored rather than raising."""
    fan_modes, speeds = get_fan_modes_and_speeds(
        {ATTR_FAN_MODES: ["low", None, "high", 3]}
    )
    assert fan_modes == {"low": "low", "high": "high"}
    assert speeds == ["low", "high"]


def test_get_swing_on_mode_none_when_no_swing_modes() -> None:
    """Test the swing helper returns None when the entity has no swing modes."""
    assert get_swing_on_mode({}) is None
    assert get_swing_on_mode({ATTR_SWING_MODES: []}) is None
    assert get_swing_on_mode({ATTR_SWING_MODES: ["custom"]}) is None
    assert get_swing_on_mode({ATTR_SWING_MODES: ["off", "vertical"]}) == "vertical"
