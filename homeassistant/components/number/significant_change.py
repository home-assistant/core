"""Helper to test significant Number state changes."""

from __future__ import annotations

from typing import Any

from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.significant_change import (
    check_absolute_change,
    check_percentage_change,
    check_valid_float,
)

from .const import NumberDeviceClass


def _absolute_and_relative_change(
    old_state: float | None,
    new_state: float | None,
    absolute_change: float,
    percentage_change: float,
) -> bool:
    return check_absolute_change(
        old_state, new_state, absolute_change
    ) and check_percentage_change(old_state, new_state, percentage_change)


@callback
def async_check_significant_change(
    hass: HomeAssistant,
    old_state: str,
    old_attrs: dict,
    new_state: str,
    new_attrs: dict,
    **kwargs: Any,
) -> bool | None:
    """Test if state significantly changed."""
    if (device_class := new_attrs.get(ATTR_DEVICE_CLASS)) is None:
        return None

    absolute_change: float | None = None
    percentage_change: float | None = None

    # special for temperature
    if device_class == NumberDeviceClass.TEMPERATURE:
        if new_attrs.get(ATTR_UNIT_OF_MEASUREMENT) == UnitOfTemperature.FAHRENHEIT:
            absolute_change = 1.0
        else:
            absolute_change = 0.5

    # special for percentage
    elif device_class in (
        NumberDeviceClass.BATTERY,
        NumberDeviceClass.HUMIDITY,
        NumberDeviceClass.MOISTURE,
    ):
        absolute_change = 1.0

    # special for power factor
    elif device_class == NumberDeviceClass.POWER_FACTOR:
        if new_attrs.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE:
            absolute_change = 1.0
        else:
            absolute_change = 0.1
            percentage_change = 2.0

    # default for all other classified
    else:
        absolute_change = 1.0
        percentage_change = 2.0

    if not check_valid_float(new_state):
        # New state is invalid, don't report it
        return False

    if not check_valid_float(old_state):
        # Old state was invalid, we should report again
        return True

    if absolute_change is not None and percentage_change is not None:
        return _absolute_and_relative_change(
            float(old_state), float(new_state), absolute_change, percentage_change
        )
    if absolute_change is not None:
        return check_absolute_change(
            float(old_state), float(new_state), absolute_change
        )
