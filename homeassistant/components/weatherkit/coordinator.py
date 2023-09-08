"""DataUpdateCoordinator for WeatherKit integration. Updated every 15 minutes."""
from __future__ import annotations

from datetime import timedelta
from typing import Literal

from apple_weatherkit.client import (
    WeatherKitApiClient,
    WeatherKitApiClientAuthenticationError,
    WeatherKitApiClientError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER


class WeatherKitDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    config_entry: ConfigEntry
    supported_data_sets: list[
        Literal["currentWeather", "forecastDaily", "forecastHourly"]
    ] | None

    def __init__(
        self,
        hass: HomeAssistant,
        client: WeatherKitApiClient,
    ) -> None:
        """Initialize."""
        self.client = client
        self.supported_data_sets = None
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=15),
        )

    async def _update_supported_data_sets(self):
        supported_data_sets = await self.client.get_availability(
            self.config_entry.data[CONF_LOCATION][CONF_LATITUDE],
            self.config_entry.data[CONF_LOCATION][CONF_LONGITUDE],
        )

        requested_data_sets = ["currentWeather", "forecastDaily", "forecastHourly"]

        self.supported_data_sets = [
            data_set
            for data_set in requested_data_sets
            if data_set in supported_data_sets
        ]

        LOGGER.debug("Supported data sets: %s", self.supported_data_sets)

    async def _async_update_data(self):
        """Update the current weather and forecasts."""
        try:
            if not self.supported_data_sets:
                await self._update_supported_data_sets()

            return await self.client.get_weather_data(
                self.config_entry.data[CONF_LOCATION][CONF_LATITUDE],
                self.config_entry.data[CONF_LOCATION][CONF_LONGITUDE],
                self.supported_data_sets,
            )
        except WeatherKitApiClientAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except WeatherKitApiClientError as exception:
            raise UpdateFailed(exception) from exception
