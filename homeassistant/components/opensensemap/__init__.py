"""The openSenseMap integration."""

from opensensemap_api import OpenSenseMap
from opensensemap_api.exceptions import OpenSenseMapError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_STATION_ID

PLATFORMS: list[Platform] = [Platform.AIR_QUALITY]

type OpenSenseMapConfigEntry = ConfigEntry[OpenSenseMap]


async def async_setup_entry(
    hass: HomeAssistant, entry: OpenSenseMapConfigEntry
) -> bool:
    """Set up openSenseMap from a config entry."""
    session = async_get_clientsession(hass)
    api = OpenSenseMap(entry.data[CONF_STATION_ID], session)
    try:
        await api.get_data()
    except OpenSenseMapError as err:
        raise ConfigEntryNotReady(
            f"Unable to fetch data from openSenseMap: {err}"
        ) from err

    entry.runtime_data = api
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: OpenSenseMapConfigEntry
) -> bool:
    """Unload an openSenseMap config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
