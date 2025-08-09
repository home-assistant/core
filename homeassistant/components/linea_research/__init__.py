"""The Linea Research integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import LineaResearchConfigEntry, LineaResearchDataUpdateCoordinator
from .tipi_client import TIPIClient, TIPIConnectionError

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: LineaResearchConfigEntry) -> bool:
    """Set up Linea Research from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    
    client = TIPIClient(host, port)
    coordinator = LineaResearchDataUpdateCoordinator(hass, entry, client)
    
    try:
        await coordinator.async_setup()
        await coordinator.async_config_entry_first_refresh()
    except TIPIConnectionError as err:
        await client.disconnect()
        raise ConfigEntryNotReady(f"Unable to connect to {host}:{port}") from err
    
    entry.runtime_data = coordinator
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LineaResearchConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator = entry.runtime_data
        await coordinator.async_shutdown()
    
    return unload_ok