"""Integration platform for recorder."""
from __future__ import annotations

from homeassistant.core import HomeAssistant, callback

from .const import (
    ATTR_FAN_MODES,
    ATTR_HVAC_MODES,
    ATTR_MAX_HUMIDITY,
    ATTR_MAX_TEMP,
    ATTR_MIN_HUMIDITY,
    ATTR_MIN_TEMP,
    ATTR_PRESET_MODES,
    ATTR_SWING_MODES,
    ATTR_TARGET_TEMP_STEP,
)


@callback
def exclude_attributes(hass: HomeAssistant) -> set[str]:
    """Exclude static attributes from being recorded in the database."""
    return {
        ATTR_HVAC_MODES,
        ATTR_FAN_MODES,
        ATTR_SWING_MODES,
        ATTR_MIN_TEMP,
        ATTR_MAX_TEMP,
        ATTR_MIN_HUMIDITY,
        ATTR_MAX_HUMIDITY,
        ATTR_TARGET_TEMP_STEP,
        ATTR_PRESET_MODES,
    }
