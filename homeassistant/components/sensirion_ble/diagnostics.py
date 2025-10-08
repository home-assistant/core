"""Diagnostics support for Sensirion BLE."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TITLE, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant

from .const import DOMAIN

TO_REDACT = {
    CONF_TITLE,
    CONF_UNIQUE_ID,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    return async_redact_data(
        {
            "entry": entry.as_dict(),
            "coordinator_data": {
                "last_update_success": coordinator.last_update_success,
                "available": coordinator.available,
                "address": coordinator.address,
                "mode": str(coordinator.mode),
            },
        },
        TO_REDACT,
    )
