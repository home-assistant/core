"""The Trimlight integration."""

from aiotrimlight import TrimlightClient

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import TrimlightConfigEntry, TrimlightCoordinator

PLATFORMS = (Platform.LIGHT,)


async def async_setup_entry(hass: HomeAssistant, entry: TrimlightConfigEntry) -> bool:
    """Set up Trimlight from a config entry."""
    client = TrimlightClient(
        entry.data[CONF_HOST],
        async_get_clientsession(hass),
    )

    coordinator = TrimlightCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TrimlightConfigEntry) -> bool:
    """Unload a Trimlight config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
