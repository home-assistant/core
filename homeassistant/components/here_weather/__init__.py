"""The here_weather component."""
import asyncio
from datetime import timedelta
import logging

import async_timeout
import herepy

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MODE,
    CONF_SCAN_INTERVAL,
    CONF_UNIT_SYSTEM,
    CONF_UNIT_SYSTEM_METRIC,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, HERE_API_KEYS

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the here_weather component."""
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up here_weather from a config entry."""
    here_weather_data = HEREWeatherData(hass, config_entry)
    await here_weather_data.async_setup()
    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = here_weather_data

    known_api_keys = hass.data.setdefault(HERE_API_KEYS, [])
    if config_entry.data[CONF_API_KEY] not in known_api_keys:
        known_api_keys.append(config_entry.data[CONF_API_KEY])

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(config_entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN][config_entry.entry_id].unsub_handler()
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


class HEREWeatherData:
    """Get the latest data from HERE."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize the data object."""
        self.hass = hass
        self.config_entry = config_entry
        self.here_client = herepy.DestinationWeatherApi(config_entry.data[CONF_API_KEY])
        self.latitude = config_entry.data[CONF_LATITUDE]
        self.longitude = config_entry.data[CONF_LONGITUDE]
        self.weather_product_type = herepy.WeatherProductType[
            config_entry.data[CONF_MODE]
        ]
        self.units = None
        self.coordinator = None
        self.unsub_handler = None

    async def async_setup(self) -> list:
        """Set up the here_weather integration."""
        self.add_options()
        self.units = self.config_entry.options[CONF_UNIT_SYSTEM]
        self.unsub_handler = self.config_entry.add_update_listener(
            self.async_options_updated
        )
        self.coordinator = DataUpdateCoordinator(
            self.hass,
            _LOGGER,
            name=DOMAIN,
            update_method=self.async_update,
            update_interval=timedelta(
                seconds=self.config_entry.options[CONF_SCAN_INTERVAL]
            ),
        )
        await self.coordinator.async_refresh()

    def add_options(self) -> None:
        """Add options for here_weather integration."""
        if not self.config_entry.options:
            options = {
                CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                CONF_UNIT_SYSTEM: self.hass.config.units.name,
            }
            self.hass.config_entries.async_update_entry(
                self.config_entry, options=options
            )

    async def async_update(self) -> None:
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
        is_metric = self.units == CONF_UNIT_SYSTEM_METRIC
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
    async def async_options_updated(
        hass: HomeAssistant, config_entry: ConfigEntry
    ) -> None:
        """Triggered by config entry options updates."""
        hass.data[DOMAIN][config_entry.entry_id].set_update_interval(
            config_entry.options[CONF_SCAN_INTERVAL]
        )

    def set_update_interval(self, update_interval: int) -> None:
        """Set the coordinator update_interval to the supplied update_interval."""
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
