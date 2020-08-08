"""The met component."""
from datetime import timedelta
import logging
from random import randrange

import metno

from homeassistant.const import (
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    LENGTH_FEET,
    LENGTH_METERS,
)
from homeassistant.core import Config, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.distance import convert as convert_distance
import homeassistant.util.dt as dt_util

from .const import CONF_TRACK_HOME, DOMAIN

URL = "https://aa015h6buqvih86i1.api.met.no/weatherapi/locationforecast/1.9/"


_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: Config) -> bool:
    """Set up configured Met."""
    return True


async def async_setup_entry(hass, config_entry):
    """Set up Met as config entry."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = dict()
    coordinator = MetDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "weather")
    )
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    await hass.config_entries.async_forward_entry_unload(config_entry, "weather")
    hass.data[DOMAIN].pop(config_entry.entry_id)
    return True


class MetDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Met data."""

    def __init__(self, hass, config_entry):
        """Initialize global Met data updater."""
        self.weather = MetWeatherData(
            hass, config_entry.data, hass.config.units.is_metric
        )
        self.weather.init_data()

        update_interval = timedelta(minutes=randrange(55, 65))

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

    async def _async_update_data(self):
        """Fetch data from Met."""
        try:
            return await self.weather.fetch_data()
        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}")


class MetWeatherData:
    """Keep data for Met.no weather entities."""

    def __init__(self, hass, config, is_metric):
        """Initialise the weather entity data."""
        self.hass = hass
        self._config = config
        self._is_metric = is_metric
        self._weather_data = None
        self.current_weather_data = {}
        self.forecast_data = None

    def init_data(self):
        """Weather data inialization - get the coordinates."""
        conf = self._config

        if conf.get(CONF_TRACK_HOME, False):
            latitude = self.hass.config.latitude
            longitude = self.hass.config.longitude
            elevation = self.hass.config.elevation
        else:
            latitude = conf[CONF_LATITUDE]
            longitude = conf[CONF_LONGITUDE]
            elevation = conf[CONF_ELEVATION]

        if not self._is_metric:
            elevation = int(
                round(convert_distance(elevation, LENGTH_FEET, LENGTH_METERS))
            )

        coordinates = {
            "lat": str(latitude),
            "lon": str(longitude),
            "msl": str(elevation),
        }
        self._weather_data = metno.MetWeatherData(
            coordinates, async_get_clientsession(self.hass), URL
        )

    async def fetch_data(self):
        """Fetch data from API - (current weather and forecast)."""
        await self._weather_data.fetching_data()
        self.current_weather_data = self._weather_data.get_current_weather()
        time_zone = dt_util.DEFAULT_TIME_ZONE
        self.forecast_data = self._weather_data.get_forecast(time_zone)
        return self
