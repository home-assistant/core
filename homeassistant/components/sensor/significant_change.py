"""Helper to test significant sensor state changes."""
from __future__ import annotations

from typing import Any

from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.significant_change import (
    check_absolute_change,
    check_percentage_change,
)

from . import (
    DEVICE_CLASS_AQI,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CO,
    DEVICE_CLASS_CO2,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_PM10,
    DEVICE_CLASS_PM25,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_VOLATILE_ORGANIC_COMPOUNDS,
)


def _absolute_and_relative_change(
    old_state: int | float | None,
    new_state: int | float | None,
    absolute_change: int | float,
    percentage_change: int | float,
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
    device_class = new_attrs.get(ATTR_DEVICE_CLASS)

    if device_class is None:
        return None

    absolute_change: float | None = None
    percentage_change: float | None = None
    if device_class == DEVICE_CLASS_TEMPERATURE:
        if new_attrs.get(ATTR_UNIT_OF_MEASUREMENT) == TEMP_FAHRENHEIT:
            absolute_change = 1.0
        else:
            absolute_change = 0.5

    if device_class in (DEVICE_CLASS_BATTERY, DEVICE_CLASS_HUMIDITY):
        absolute_change = 1.0

    if device_class in (
        DEVICE_CLASS_AQI,
        DEVICE_CLASS_CO,
        DEVICE_CLASS_CO2,
        DEVICE_CLASS_PM25,
        DEVICE_CLASS_PM10,
        DEVICE_CLASS_VOLATILE_ORGANIC_COMPOUNDS,
    ):
        absolute_change = 1.0
        percentage_change = 2.0

    if absolute_change is not None and percentage_change is not None:
        return _absolute_and_relative_change(
            float(old_state), float(new_state), absolute_change, percentage_change
        )
    if absolute_change is not None:
        return check_absolute_change(
            float(old_state), float(new_state), absolute_change
        )

    return None
