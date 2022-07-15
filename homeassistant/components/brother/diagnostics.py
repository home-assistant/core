"""Diagnostics support for Brother."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import BrotherDataUpdateCoordinator
from .const import DATA_CONFIG_ENTRY, DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict:
    """Return diagnostics for a config entry."""
    coordinator: BrotherDataUpdateCoordinator = hass.data[DOMAIN][DATA_CONFIG_ENTRY][
        config_entry.entry_id
    ]

    diagnostics_data = {
        "info": dict(config_entry.data),
        "data": coordinator.data,
    }

    return diagnostics_data
