"""Integration platform for recorder."""
from __future__ import annotations

from homeassistant.core import HomeAssistant, callback

from . import (
    STATE_ATTR_AZIMUTH,
    STATE_ATTR_ELEVATION,
    STATE_ATTR_NEXT_DAWN,
    STATE_ATTR_NEXT_DUSK,
    STATE_ATTR_NEXT_MIDNIGHT,
    STATE_ATTR_NEXT_NOON,
    STATE_ATTR_NEXT_RISING,
    STATE_ATTR_NEXT_SETTING,
    STATE_ATTR_RISING,
)


@callback
def exclude_attributes(hass: HomeAssistant) -> set[str]:
    """Exclude sun attributes from being recorded in the database."""
    return {
        STATE_ATTR_AZIMUTH,
        STATE_ATTR_ELEVATION,
        STATE_ATTR_RISING,
        STATE_ATTR_NEXT_DAWN,
        STATE_ATTR_NEXT_DUSK,
        STATE_ATTR_NEXT_MIDNIGHT,
        STATE_ATTR_NEXT_NOON,
        STATE_ATTR_NEXT_RISING,
        STATE_ATTR_NEXT_SETTING,
    }
