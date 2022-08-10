"""Integration platform for recorder."""
from __future__ import annotations

from homeassistant.const import ATTR_EDITABLE
from homeassistant.core import HomeAssistant, callback

from .const import (
    ATTR_FRIDAY,
    ATTR_MONDAY,
    ATTR_NEXT_EVENT,
    ATTR_SATURDAY,
    ATTR_SUNDAY,
    ATTR_THURSDAY,
    ATTR_TUESDAY,
    ATTR_WEDNESDAY,
)


@callback
def exclude_attributes(hass: HomeAssistant) -> set[str]:
    """Exclude configuration to be recorded in the database."""
    return {
        ATTR_EDITABLE,
        ATTR_FRIDAY,
        ATTR_MONDAY,
        ATTR_SATURDAY,
        ATTR_SUNDAY,
        ATTR_THURSDAY,
        ATTR_TUESDAY,
        ATTR_WEDNESDAY,
        ATTR_NEXT_EVENT,
    }
