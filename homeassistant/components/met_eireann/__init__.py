"""The met_eireann component."""

from datetime import timedelta
import logging
from types import MappingProxyType
from typing import Any, Self

import meteireann

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ELEVATION, CONF_LATITUDE, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(minutes=60)

PLATFORMS = [Platform.WEATHER]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Met Éireann as config entry."""
    hass.data.setdefault(DOMAIN, {})

    raw_weather_data = meteireann.WeatherData(
        async_get_clientsession(hass),
        latitude=config_entry.data[CONF_LATITUDE],
        longitude=config_entry.data[CONF_LONGITUDE],
        altitude=config_entry.data[CONF_ELEVATION],
    )

    weather_data = MetEireannWeatherData(config_entry.data, raw_weather_data)

    async def _async_update_data() -> MetEireannWeatherData:
        """Fetch data from Met Éireann."""
        try:
            return await weather_data.fetch_data()
        except Exception as err:
            raise UpdateFailed(f"Update failed: {err}") from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        config_entry=config_entry,
        name=DOMAIN,
        update_method=_async_update_data,
        update_interval=UPDATE_INTERVAL,
    )
    await coordinator.async_refresh()

    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


class MetEireannWeatherData:
    """Keep data for Met Éireann weather entities."""

    def __init__(
        self, config: MappingProxyType[str, Any], weather_data: meteireann.WeatherData
    ) -> None:
        """Initialise the weather entity data."""
        self._config = config
        self._weather_data = weather_data
        self.current_weather_data: dict[str, Any] = {}
        self.daily_forecast: list[dict[str, Any]] = []
        self.hourly_forecast: list[dict[str, Any]] = []

    async def fetch_data(self) -> Self:
        """Fetch data from API - (current weather and forecast)."""
        await self._weather_data.fetching_data()
        self.current_weather_data = self._weather_data.get_current_weather()
        time_zone = dt_util.get_default_time_zone()
        self.daily_forecast = self._weather_data.get_forecast(time_zone, False)
        self.hourly_forecast = self._weather_data.get_forecast(time_zone, True)
        return self
