"""Integration platform for recorder."""
from __future__ import annotations

from homeassistant.core import HomeAssistant, callback

from . import ATTR_CUR, ATTR_LAST_ACTION, ATTR_LAST_TRIGGERED, ATTR_MAX, ATTR_MODE


@callback
def exclude_attributes(hass: HomeAssistant) -> set[str]:
    """Exclude extra attributes from being recorded in the database."""
    return {ATTR_LAST_TRIGGERED, ATTR_MODE, ATTR_CUR, ATTR_MAX, ATTR_LAST_ACTION}
