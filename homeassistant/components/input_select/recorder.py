"""Integration platform for recorder."""
from __future__ import annotations

from homeassistant.const import ATTR_EDITABLE
from homeassistant.core import HomeAssistant, callback

from . import ATTR_OPTIONS


@callback
def exclude_attributes(hass: HomeAssistant) -> set[str]:
    """Exclude editable hint and options from being recorded in the database."""
    return {ATTR_EDITABLE, ATTR_OPTIONS}
