"""Integration platform for recorder."""
from __future__ import annotations

from homeassistant.const import ATTR_EDITABLE
from homeassistant.core import HomeAssistant, callback

from . import CONF_HAS_DATE, CONF_HAS_TIME


@callback
def exclude_attributes(hass: HomeAssistant) -> set[str]:
    """Exclude some attributes from being recorded in the database."""
    return {ATTR_EDITABLE, CONF_HAS_DATE, CONF_HAS_TIME}
