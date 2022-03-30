"""Integration platform for recorder."""
from __future__ import annotations

from homeassistant.core import HomeAssistant, callback

from . import ATTR_IN_PROGRESS


@callback
def exclude_attributes(hass: HomeAssistant) -> set[str]:
    """Exclude update in progress attribute from being recorded in the database."""
    return {ATTR_IN_PROGRESS}
