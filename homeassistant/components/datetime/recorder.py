"""Integration platform for recorder."""
from __future__ import annotations

from homeassistant.core import HomeAssistant, callback

from . import (
    ATTR_DAY,
    ATTR_HOUR,
    ATTR_MINUTE,
    ATTR_MONTH,
    ATTR_SECOND,
    ATTR_TIMESTAMP,
    ATTR_YEAR,
)


@callback
def exclude_attributes(hass: HomeAssistant) -> set[str]:
    """Exclude static attributes from being recorded in the database."""
    return {
        ATTR_DAY,
        ATTR_HOUR,
        ATTR_MINUTE,
        ATTR_MONTH,
        ATTR_SECOND,
        ATTR_TIMESTAMP,
        ATTR_YEAR,
    }
