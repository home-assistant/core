"""Integration platform for recorder."""
from __future__ import annotations

from homeassistant.const import ATTR_EDITABLE
from homeassistant.core import HomeAssistant, callback

from .const import ATTR_NEXT_EVENT


@callback
def exclude_attributes(hass: HomeAssistant) -> set[str]:
    """Exclude configuration to be recorded in the database."""
    return {
        ATTR_EDITABLE,
        ATTR_NEXT_EVENT,
    }
