"""utility functions for the Reolink component."""
from __future__ import annotations

from homeassistant import config_entries
from homeassistant.core import HomeAssistant

from . import ReolinkData
from .const import DOMAIN


def has_connection_problem(
    hass: HomeAssistant, config_entry: config_entries.ConfigEntry
) -> bool:
    """Check if a existing entry has a connection problem."""
    reolink_data: ReolinkData | None = hass.data.get(DOMAIN, {}).get(
        config_entry.entry_id
    )
    connection_problem = (
        reolink_data is not None
        and config_entry.state == config_entries.ConfigEntryState.LOADED
        and reolink_data.device_coordinator.last_update_success
    )
    return connection_problem
