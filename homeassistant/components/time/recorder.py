"""Integration platform for recorder."""
from __future__ import annotations

from homeassistant.core import HomeAssistant, callback

from . import ATTR_HOUR, ATTR_MINUTE, ATTR_SECOND


@callback
def exclude_attributes(hass: HomeAssistant) -> set[str]:
    """Exclude static attributes from being recorded in the database."""
    return {ATTR_HOUR, ATTR_MINUTE, ATTR_SECOND}
