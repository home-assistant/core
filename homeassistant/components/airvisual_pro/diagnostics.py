"""Support for AirVisual Pro diagnostics."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

CONF_MAC_ADDRESS = "mac_address"
CONF_SERIAL_NUMBER = "serial_number"

TO_REDACT = {
    CONF_MAC_ADDRESS,
    CONF_PASSWORD,
    CONF_SERIAL_NUMBER,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
        },
        "data": async_redact_data(coordinator.data, TO_REDACT),
    }
