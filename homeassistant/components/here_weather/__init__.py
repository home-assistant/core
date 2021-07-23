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
    CONF_UNIT_SYSTEM_METRIC,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_MODES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_UPDATE_RATE_FOR_ONE_CLIENT,
)
from .utils import active_here_clients

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "weather"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up here_weather from a config entry."""
    here_weather_coordinators = {}
    for mode in CONF_MODES:
        coordinator = HEREWeatherDataUpdateCoordinator(hass, entry, mode)
        await coordinator.async_config_entry_first_refresh()
        here_weather_coordinators[mode] = coordinator
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = here_weather_coordinators

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class HEREWeatherDataUpdateCoordinator(DataUpdateCoordinator):
    """Get the latest data from HERE."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, mode: str) -> None:
        """Initialize the data object."""
        self.here_client = herepy.DestinationWeatherApi(entry.data[CONF_API_KEY])
        self.latitude = entry.data[CONF_LATITUDE]
        self.longitude = entry.data[CONF_LONGITUDE]
        self.weather_product_type = herepy.WeatherProductType[mode]

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    def number_of_listeners(self) -> int:
        """Return the number ob active listeners registered against this coordinator."""
        return len(self._listeners)

    async def _async_update_data(self) -> list:
        """Perform data update."""
        try:
            async with async_timeout.timeout(10):
                data = await self.hass.async_add_executor_job(self._get_data)
                self._set_update_interval()
                return data
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

    def _set_update_interval(self) -> int:
        """Throttle the default update rate based on the number of active clients."""
        if (
            update_interval := (
                active_here_clients(self.hass) * MAX_UPDATE_RATE_FOR_ONE_CLIENT * 2
            )
        ) > DEFAULT_SCAN_INTERVAL:
            _LOGGER.debug("Setting update_interval to %s", update_interval)
            return update_interval
        return DEFAULT_SCAN_INTERVAL


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
