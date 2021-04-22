"""Helper to test significant sensor state changes."""
from __future__ import annotations

from typing import Any

from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant, callback

from . import DEVICE_CLASS_BATTERY, DEVICE_CLASS_HUMIDITY, DEVICE_CLASS_TEMPERATURE


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

    if device_class == DEVICE_CLASS_TEMPERATURE:
        if new_attrs.get(ATTR_UNIT_OF_MEASUREMENT) == TEMP_FAHRENHEIT:
            change: float | int = 1
        else:
            change = 0.5

        old_value = float(old_state)
        new_value = float(new_state)
        return abs(old_value - new_value) >= change

    if device_class in (DEVICE_CLASS_BATTERY, DEVICE_CLASS_HUMIDITY):
        old_value = float(old_state)
        new_value = float(new_state)

        return abs(old_value - new_value) >= 1

    return None
