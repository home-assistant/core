"""Integration for NexBlue EV chargers."""

from nexblue_api import NexBlueClient

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_API_URL, PLATFORMS
from .coordinator import NexBlueConfigEntry, NexBlueDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: NexBlueConfigEntry) -> bool:
    """Set up NexBlue from a config entry."""
    client = NexBlueClient(async_get_clientsession(hass), DEFAULT_API_URL)
    coordinator = NexBlueDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NexBlueConfigEntry) -> bool:
    """Unload a NexBlue config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
