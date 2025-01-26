"""Utilities for deCONZ integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .hub import DeconzHub


def serial_from_unique_id(unique_id: str | None) -> str | None:
    """Get a device serial number from a unique ID, if possible."""
    if not unique_id or unique_id.count(":") != 7:
        return None
    return unique_id.partition("-")[0]


@callback
def get_master_hub(hass: HomeAssistant) -> DeconzHub:
    """Return the gateway which is marked as master."""
    hub: DeconzHub
    for hub in hass.data[DOMAIN].values():
        if hub.master:
            return hub
    raise ValueError
