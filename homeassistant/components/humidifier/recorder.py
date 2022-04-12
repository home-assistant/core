"""Integration platform for recorder."""
from __future__ import annotations

from homeassistant.core import HomeAssistant, callback

from . import ATTR_AVAILABLE_MODES, ATTR_MAX_HUMIDITY, ATTR_MIN_HUMIDITY


@callback
def exclude_attributes(hass: HomeAssistant) -> set[str]:
    """Exclude static attributes from being recorded in the database."""
    return {
        ATTR_MIN_HUMIDITY,
        ATTR_MAX_HUMIDITY,
        ATTR_AVAILABLE_MODES,
    }
