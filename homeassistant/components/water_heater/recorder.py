"""Integration platform for recorder."""
from __future__ import annotations

from homeassistant.core import HomeAssistant, callback

from . import ATTR_MAX_TEMP, ATTR_MIN_TEMP, ATTR_OPERATION_LIST


@callback
def exclude_attributes(hass: HomeAssistant) -> set[str]:
    """Exclude static attributes from being recorded in the database."""
    return {ATTR_OPERATION_LIST, ATTR_MIN_TEMP, ATTR_MAX_TEMP}
