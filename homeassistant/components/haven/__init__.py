"""HAVEN IAQ local API integration."""

from haveniaq import HavenClient

from homeassistant.const import CONF_HOST, CONF_PATH, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_PATH, DEFAULT_PORT
from .coordinator import HavenConfigEntry, HavenDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: HavenConfigEntry) -> bool:
    """Set up HAVEN IAQ from a config entry."""
    session = async_get_clientsession(hass)
    client = HavenClient(
        entry.data[CONF_HOST],
        session=session,
        port=entry.data.get(CONF_PORT, DEFAULT_PORT),
        path=entry.data.get(CONF_PATH, DEFAULT_PATH),
    )

    coordinator = HavenDataUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HavenConfigEntry) -> bool:
    """Unload a HAVEN IAQ config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
