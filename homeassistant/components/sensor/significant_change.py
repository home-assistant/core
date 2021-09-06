"""Helper to test significant sensor state changes."""
from __future__ import annotations

from typing import Any, Callable

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

    change: float | None = None
    condition: Callable[[int | float, int | float, int | float], bool] | None = None
    if device_class == DEVICE_CLASS_TEMPERATURE:
        if new_attrs.get(ATTR_UNIT_OF_MEASUREMENT) == TEMP_FAHRENHEIT:
            change = 1.0
        else:
            change = 0.5
        condition = check_absolute_change

    if device_class in (DEVICE_CLASS_BATTERY, DEVICE_CLASS_HUMIDITY):
        change = 1.0
        condition = check_absolute_change

    if device_class in (
        DEVICE_CLASS_AQI,
        DEVICE_CLASS_CO,
        DEVICE_CLASS_CO2,
        DEVICE_CLASS_PM25,
        DEVICE_CLASS_PM10,
        DEVICE_CLASS_VOLATILE_ORGANIC_COMPOUNDS,
    ):
        change = 2.0
        condition = check_percentage_change

    if change is not None and condition is not None:
        return condition(float(old_state), float(new_state), change)

    return None
