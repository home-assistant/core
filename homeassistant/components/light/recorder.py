"""Integration platform for recorder."""
from __future__ import annotations

from homeassistant.core import HomeAssistant, callback

from . import (
    ATTR_EFFECT_LIST,
    ATTR_MAX_MIREDS,
    ATTR_MIN_MIREDS,
    ATTR_SUPPORTED_COLOR_MODES,
)


@callback
def exclude_attributes(hass: HomeAssistant) -> set[str]:
    """Exclude static attributes from being recorded in the database."""
    return {
        ATTR_SUPPORTED_COLOR_MODES,
        ATTR_EFFECT_LIST,
        ATTR_MIN_MIREDS,
        ATTR_MAX_MIREDS,
    }
