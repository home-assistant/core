"""Integration platform for recorder."""
from __future__ import annotations

from homeassistant.core import HomeAssistant, callback

from . import ATTR_HAS_DATE, ATTR_HAS_TIME, ATTR_MODE


@callback
def exclude_attributes(hass: HomeAssistant) -> set[str]:
    """Exclude static attributes from being recorded in the database."""
    return {ATTR_HAS_DATE, ATTR_HAS_TIME, ATTR_MODE}
