"""The AEMET OpenData component."""

from aemet_opendata.exceptions import TownNotFound
from aemet_opendata.interface import AEMET, ConnectionOptions

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .const import (
    CONF_STATION_UPDATES,
    DOMAIN,
    ENTRY_NAME,
    ENTRY_WEATHER_COORDINATOR,
    PLATFORMS,
)
from .weather_update_coordinator import WeatherUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up AEMET OpenData as config entry."""
    name = entry.data[CONF_NAME]
    api_key = entry.data[CONF_API_KEY]
    latitude = entry.data[CONF_LATITUDE]
    longitude = entry.data[CONF_LONGITUDE]
    station_updates = entry.options.get(CONF_STATION_UPDATES, True)

    options = ConnectionOptions(api_key, station_updates)
    aemet = AEMET(aiohttp_client.async_get_clientsession(hass), options)
    try:
        await aemet.select_coordinates(latitude, longitude)
    except TownNotFound:
        return False

    weather_coordinator = WeatherUpdateCoordinator(hass, aemet)
    await weather_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        ENTRY_NAME: name,
        ENTRY_WEATHER_COORDINATOR: weather_coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
