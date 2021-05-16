"""The met_eireann component."""
from datetime import timedelta
import logging

import meteireann

from homeassistant.const import CONF_ELEVATION, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(minutes=60)

PLATFORMS = ["weather"]


async def async_setup_entry(hass, config_entry):
    """Set up Met Éireann as config entry."""
    hass.data.setdefault(DOMAIN, {})

    raw_weather_data = meteireann.WeatherData(
        async_get_clientsession(hass),
        latitude=config_entry.data[CONF_LATITUDE],
        longitude=config_entry.data[CONF_LONGITUDE],
        altitude=config_entry.data[CONF_ELEVATION],
    )

    weather_data = MetEireannWeatherData(hass, config_entry.data, raw_weather_data)

    async def _async_update_data():
        """Fetch data from Met Éireann."""
        try:
            return await weather_data.fetch_data()
        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=_async_update_data,
        update_interval=UPDATE_INTERVAL,
    )
    await coordinator.async_refresh()

    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


class MetEireannWeatherData:
    """Keep data for Met Éireann weather entities."""

    def __init__(self, hass, config, weather_data):
        """Initialise the weather entity data."""
        self.hass = hass
        self._config = config
        self._weather_data = weather_data
        self.current_weather_data = {}
        self.daily_forecast = None
        self.hourly_forecast = None

    async def fetch_data(self):
        """Fetch data from API - (current weather and forecast)."""
        await self._weather_data.fetching_data()
        self.current_weather_data = self._weather_data.get_current_weather()
        time_zone = dt_util.DEFAULT_TIME_ZONE
        self.daily_forecast = self._weather_data.get_forecast(time_zone, False)
        self.hourly_forecast = self._weather_data.get_forecast(time_zone, True)
        return self
