"""The Osmund integration: electricity prices from the Osmund API."""

from osmund import OsmundClient

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import OsmundConfigEntry, OsmundCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: OsmundConfigEntry) -> None:
    """Set up Osmund from a config entry."""
    client = OsmundClient(async_get_clientsession(hass), entry.data[CONF_API_KEY])
    coordinator = OsmundCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: OsmundConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
