"""Diagnostics support for CO2Signal."""
from __future__ import annotations

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from . import DOMAIN, CO2SignalCoordinator

TO_REDACT = {CONF_API_KEY}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict:
    """Return diagnostics for a config entry."""
    coordinator: CO2SignalCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    return {
        "config_entry": async_redact_data(config_entry.as_dict(), TO_REDACT),
        "data": coordinator.data,
    }
