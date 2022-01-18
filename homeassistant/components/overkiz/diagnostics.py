"""Provides diagnostics for Overkiz."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import HomeAssistantOverkizData
from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> list[dict]:
    """Return diagnostics for a config entry."""
    data: HomeAssistantOverkizData = hass.data[DOMAIN][entry.entry_id]
    client = data.coordinator.client
    setup = client.get_diagnostic_data()

    return [setup]
