"""The BirdNET-Go integration."""

from aiobirdnetgo import BirdNetGoClient

from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import BirdNetGoConfigEntry, BirdNetGoDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: BirdNetGoConfigEntry) -> bool:
    """Set up BirdNET-Go from a config entry."""
    client = BirdNetGoClient(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        use_ssl=entry.data[CONF_SSL],
        session=async_get_clientsession(hass),
    )

    coordinator = BirdNetGoDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: BirdNetGoConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
