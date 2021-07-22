"""The here_weather component."""
from __future__ import annotations

from datetime import timedelta
import logging

import async_timeout
import herepy

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_SCAN_INTERVAL,
    CONF_UNIT_SYSTEM_METRIC,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_MODES, DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "weather"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up here_weather from a config entry."""
    here_weather_data_dict = {}
    for mode in CONF_MODES:
        here_weather_data = HEREWeatherData(hass, entry, mode)
        await here_weather_data.async_setup()
        here_weather_data_dict[mode] = here_weather_data
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = here_weather_data_dict

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class HEREWeatherData:
    """Get the latest data from HERE."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, mode: str) -> None:
        """Initialize the data object."""
        self.hass = hass
        self.entry = entry
        self.here_client = herepy.DestinationWeatherApi(entry.data[CONF_API_KEY])
        self.latitude = entry.data[CONF_LATITUDE]
        self.longitude = entry.data[CONF_LONGITUDE]
        self.weather_product_type = herepy.WeatherProductType[mode]
        self.coordinator: DataUpdateCoordinator | None = None

    async def async_setup(self) -> None:
        """Set up the here_weather integration."""
        self.add_options()
        self.entry.async_on_unload(
            self.entry.add_update_listener(self.async_options_updated)
        )
        self.coordinator = DataUpdateCoordinator(
            self.hass,
            _LOGGER,
            name=DOMAIN,
            update_method=self.async_update,
            update_interval=timedelta(seconds=self.entry.options[CONF_SCAN_INTERVAL]),
        )
        await self.coordinator.async_config_entry_first_refresh()

    def add_options(self) -> None:
        """Add options for here_weather integration."""
        if not self.entry.options:
            options = {
                CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            }
            self.hass.config_entries.async_update_entry(self.entry, options=options)

    async def async_update(self):
        """Handle data update with the DataUpdateCoordinator."""
        try:
            async with async_timeout.timeout(10):
                return await self.hass.async_add_executor_job(self._get_data)
        except herepy.InvalidRequestError as error:
            raise UpdateFailed(
                f"Unable to fetch data from HERE: {error.message}"
            ) from error

    def _get_data(self):
        """Get the latest data from HERE."""
        is_metric = self.hass.config.units.name == CONF_UNIT_SYSTEM_METRIC
        data = self.here_client.weather_for_coordinates(
            self.latitude,
            self.longitude,
            self.weather_product_type,
            metric=is_metric,
        )
        return extract_data_from_payload_for_product_type(
            data, self.weather_product_type
        )

    @staticmethod
    async def async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Triggered by config entry options updates."""
        for mode in CONF_MODES:
            hass.data[DOMAIN][entry.entry_id][mode].set_update_interval(
                entry.options[CONF_SCAN_INTERVAL]
            )

    def set_update_interval(self, update_interval: int) -> None:
        """Set the coordinator update_interval to the supplied update_interval."""
        if self.coordinator is not None:
            self.coordinator.update_interval = timedelta(seconds=update_interval)


def extract_data_from_payload_for_product_type(
    data: herepy.DestinationWeatherResponse, product_type: herepy.WeatherProductType
) -> list:
    """Extract the actual data from the HERE payload."""
    if product_type == herepy.WeatherProductType.forecast_astronomy:
        return data.astronomy["astronomy"]
    if product_type == herepy.WeatherProductType.observation:
        return data.observations["location"][0]["observation"]
    if product_type == herepy.WeatherProductType.forecast_7days:
        return data.forecasts["forecastLocation"]["forecast"]
    if product_type == herepy.WeatherProductType.forecast_7days_simple:
        return data.dailyForecasts["forecastLocation"]["forecast"]
    if product_type == herepy.WeatherProductType.forecast_hourly:
        return data.hourlyForecasts["forecastLocation"]["forecast"]
    _LOGGER.debug("Payload malformed: %s", data)
    raise UpdateFailed("Payload malformed")
