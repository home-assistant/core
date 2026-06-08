"""The openSenseMap integration."""

from opensensemap_api import OpenSenseMap

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_STATION_ID
from .coordinator import OpenSenseMapConfigEntry, OpenSenseMapCoordinator

PLATFORMS: list[Platform] = [Platform.AIR_QUALITY]


async def async_setup_entry(
    hass: HomeAssistant, entry: OpenSenseMapConfigEntry
) -> bool:
    """Set up openSenseMap from a config entry."""
    session = async_get_clientsession(hass)
    api = OpenSenseMap(entry.data[CONF_STATION_ID], session)
    coordinator = OpenSenseMapCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: OpenSenseMapConfigEntry
) -> bool:
    """Unload an openSenseMap config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
