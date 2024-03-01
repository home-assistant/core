"""The opensensemap component."""

from opensensemap_api import OpenSenseMap

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_STATION_ID, DOMAIN, PLATFORMS
from .coordinator import OpenSenseMapDataUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a opensensemap station from config entry."""

    station_id = entry.data[CONF_STATION_ID]
    station_api = OpenSenseMap(station_id, async_get_clientsession(hass))
    coordinator = OpenSenseMapDataUpdateCoordinator(hass, station_api, entry)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload opensensemap config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)
    return unload_ok
