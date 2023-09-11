"""Utility functions for the Reolink component."""
from __future__ import annotations

from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from . import ReolinkData
from .const import DOMAIN


def is_connected(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry
) -> bool:
    """Check if a existing entry has a proper connection."""
    reolink_data: ReolinkData | None = hass.data.get(DOMAIN, {}).get(
        config_entry.entry_id
    )
    is_connected = (
        reolink_data is not None
        and config_entry.state == config_entries.ConfigEntryState.LOADED
        and reolink_data.device_coordinator.last_update_success
    )
    return is_connected
