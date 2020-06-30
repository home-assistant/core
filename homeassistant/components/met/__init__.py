"""The met component."""
import metno
from homeassistant.core import Config, HomeAssistant
from homeassistant.const import (
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    LENGTH_FEET,
    LENGTH_METERS,
)
from .config_flow import MetFlowHandler
from .const import DOMAIN, CONF_TRACK_HOME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.distance import convert as convert_distance
from homeassistant.util.pressure import convert as convert_pressure
import homeassistant.util.dt as dt_util


async def async_setup(hass: HomeAssistant, config: Config) -> bool:
    """Set up configured Met."""
    return True


URL = "https://aa015h6buqvih86i1.api.met.no/weatherapi/locationforecast/1.9/"


async def async_setup_entry(hass, config_entry):
    """Set up Met as config entry."""
    unique_id = (
        f"{config_entry.data[CONF_LATITUDE]}-{config_entry.data[CONF_LONGITUDE]}"
    )
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = dict()
    hass.data[DOMAIN][unique_id] = MetWeatherData(
        hass, config_entry.data, hass.config.units.is_metric
    )
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, "weather")
    )
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    unique_id = (
        f"{config_entry.data[CONF_LATITUDE]}-{config_entry.data[CONF_LONGITUDE]}"
    )
    del hass.data[DOMAIN][unique_id]
    await hass.config_entries.async_forward_entry_unload(config_entry, "weather")
    return True


class MetWeatherData:
    """Keep data for Met.no weather entities"""

    def __init__(self, hass, config, is_metric):
        """Initialise the weather entity data"""
        self.hass = hass
        self._config = config
        self._is_metric = is_metric
        self._weather_data = None
        self.current_weather_data = {}
        self.forecast_data = None

    def init_data(self):
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
        await self._weather_data.fetching_data()
        self.current_weather_data = self._weather_data.get_current_weather()
        time_zone = dt_util.DEFAULT_TIME_ZONE
        self.forecast_data = self._weather_data.get_forecast(time_zone)
        return self
