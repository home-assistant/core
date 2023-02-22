"""Integration platform for recorder."""
from __future__ import annotations

from homeassistant.const import ATTR_EDITABLE
from homeassistant.core import HomeAssistant, callback


@callback
def exclude_attributes(hass: HomeAssistant) -> set[str]:
    """Exclude editable hint from being recorded in the database."""
    return {ATTR_EDITABLE}
