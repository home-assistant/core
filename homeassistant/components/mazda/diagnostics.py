"""Diagnostics support for the Mazda integration."""
from __future__ import annotations

from homeassistant.components.diagnostics.util import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import DATA_COORDINATOR, DOMAIN

TO_REDACT_INFO = [CONF_EMAIL, CONF_PASSWORD]
TO_REDACT_DATA = ["vin", "id", "latitude", "longitude"]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][DATA_COORDINATOR]

    diagnostics_data = {
        "info": async_redact_data(config_entry.data, TO_REDACT_INFO),
        "data": [
            async_redact_data(vehicle, TO_REDACT_DATA) for vehicle in coordinator.data
        ],
    }

    return diagnostics_data
