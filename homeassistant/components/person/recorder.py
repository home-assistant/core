"""Integration platform for recorder."""
from __future__ import annotations

from homeassistant.core import HomeAssistant, callback

from . import ATTR_DEVICE_TRACKERS


@callback
def exclude_attributes(hass: HomeAssistant) -> set[str]:
    """Exclude large and chatty update attributes from being recorded."""
    return {ATTR_DEVICE_TRACKERS}
