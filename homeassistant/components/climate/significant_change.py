"""Helper to test significant Climate state changes."""

from __future__ import annotations

from typing import Any

from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.significant_change import (
    check_absolute_change,
    check_valid_float,
)

from . import (
    ATTR_AUX_HEAT,
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_HUMIDITY,
    ATTR_HVAC_ACTION,
    ATTR_PRESET_MODE,
    ATTR_SWING_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TEMPERATURE,
)

SIGNIFICANT_ATTRIBUTES: set[str] = {
    ATTR_AUX_HEAT,
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_HUMIDITY,
    ATTR_HVAC_ACTION,
    ATTR_PRESET_MODE,
    ATTR_SWING_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ATTR_TEMPERATURE,
}


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
    if old_state != new_state:
        return True

    old_attrs_s = set(
        {k: v for k, v in old_attrs.items() if k in SIGNIFICANT_ATTRIBUTES}.items()
    )
    new_attrs_s = set(
        {k: v for k, v in new_attrs.items() if k in SIGNIFICANT_ATTRIBUTES}.items()
    )

    changed_attrs: set[str] = {item[0] for item in old_attrs_s ^ new_attrs_s}
    ha_unit = hass.config.units.temperature_unit

    for attr_name in changed_attrs:
        if attr_name in [
            ATTR_AUX_HEAT,
            ATTR_FAN_MODE,
            ATTR_HVAC_ACTION,
            ATTR_PRESET_MODE,
            ATTR_SWING_MODE,
        ]:
            return True

        old_attr_value = old_attrs.get(attr_name)
        new_attr_value = new_attrs.get(attr_name)
        if new_attr_value is None or not check_valid_float(new_attr_value):
            # New attribute value is invalid, ignore it
            continue

        if old_attr_value is None or not check_valid_float(old_attr_value):
            # Old attribute value was invalid, we should report again
            return True

        absolute_change: float | None = None
        if attr_name in [
            ATTR_CURRENT_TEMPERATURE,
            ATTR_TARGET_TEMP_HIGH,
            ATTR_TARGET_TEMP_LOW,
            ATTR_TEMPERATURE,
        ]:
            if ha_unit == UnitOfTemperature.FAHRENHEIT:
                absolute_change = 1.0
            else:
                absolute_change = 0.5

        if attr_name in [ATTR_CURRENT_HUMIDITY, ATTR_HUMIDITY]:
            absolute_change = 1.0

        if absolute_change and check_absolute_change(
            old_attr_value, new_attr_value, absolute_change
        ):
            return True

    # no significant attribute change detected
    return False
