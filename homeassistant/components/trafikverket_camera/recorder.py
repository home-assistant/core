"""Integration platform for recorder."""
from __future__ import annotations

from homeassistant.const import ATTR_LOCATION
from homeassistant.core import HomeAssistant, callback

from .const import ATTR_DESCRIPTION


@callback
def exclude_attributes(hass: HomeAssistant) -> set[str]:
    """Exclude description and location from being recorded in the database."""
    return {ATTR_DESCRIPTION, ATTR_LOCATION}
