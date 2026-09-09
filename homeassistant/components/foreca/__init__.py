"""The Foreca integration."""

from pyforeca import ForecaApiClient

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import ForecaConfigEntry, ForecaUpdateCoordinator

PLATFORMS = [Platform.WEATHER]


async def async_setup_entry(hass: HomeAssistant, entry: ForecaConfigEntry) -> bool:
    """Set up Foreca from a config entry."""
    client = ForecaApiClient(
        entry.data[CONF_API_KEY], session=async_get_clientsession(hass)
    )

    coordinators: dict[str, ForecaUpdateCoordinator] = {}
    for subentry in entry.subentries.values():
        coordinator = ForecaUpdateCoordinator(hass, entry, subentry, client)
        await coordinator.async_config_entry_first_refresh()
        coordinators[subentry.subentry_id] = coordinator

    entry.runtime_data = coordinators
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ForecaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
