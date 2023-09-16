"""Integration platform for recorder."""
from __future__ import annotations

from homeassistant.core import HomeAssistant, callback

from . import ATTR_MAX, ATTR_MIN, ATTR_MODE, ATTR_PATTERN


@callback
def exclude_attributes(hass: HomeAssistant) -> set[str]:
    """Exclude static attributes from being recorded in the database."""
    return {ATTR_MAX, ATTR_MIN, ATTR_MODE, ATTR_PATTERN}
