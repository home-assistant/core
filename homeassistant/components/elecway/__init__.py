"""The Elecway local storage integration."""

from aioelecway import StorageClient

from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import ElecwayConfigEntry, ElecwayCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ElecwayConfigEntry) -> bool:
    """Set up storage sensors after receiving a live device report."""
    client = StorageClient(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        entry.unique_id,
    )
    coordinator = ElecwayCoordinator(hass, entry, client)
    try:
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        await client.disconnect()
        raise
    entry.async_create_background_task(
        hass, coordinator.async_listen(), "Elecway storage listener"
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ElecwayConfigEntry) -> bool:
    """Unload sensors; the entry cancels its listener and closes the WebSocket."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
