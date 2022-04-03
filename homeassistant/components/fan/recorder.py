"""Integration platform for recorder."""
from __future__ import annotations

from homeassistant.core import HomeAssistant, callback

from . import ATTR_PRESET_MODES


@callback
def exclude_attributes(hass: HomeAssistant) -> set[str]:
    """Exclude static attributes from being recorded in the database."""
    return {ATTR_PRESET_MODES}
