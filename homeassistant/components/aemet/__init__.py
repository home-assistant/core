"""The AEMET OpenData component."""

from dataclasses import dataclass
import logging

from aemet_opendata.exceptions import AemetError, TownNotFound
from aemet_opendata.interface import AEMET, ConnectionOptions

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client

from .const import CONF_STATION_UPDATES, PLATFORMS
from .coordinator import WeatherUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

type AemetConfigEntry = ConfigEntry[AemetData]


@dataclass
class AemetData:
    """Aemet runtime data."""

    name: str
    coordinator: WeatherUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: AemetConfigEntry) -> bool:
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
    except TownNotFound as err:
        _LOGGER.error(err)
        return False
    except AemetError as err:
        raise ConfigEntryNotReady(err) from err

    weather_coordinator = WeatherUpdateCoordinator(hass, aemet)
    await weather_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = AemetData(name=name, coordinator=weather_coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Update options."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
