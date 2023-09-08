"""DataUpdateCoordinator for WeatherKit integration. Updated every 15 minutes."""
from __future__ import annotations

from datetime import timedelta

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

    def __init__(
        self,
        hass: HomeAssistant,
        client: WeatherKitApiClient,
    ) -> None:
        """Initialize."""
        self.client = client
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=15),
        )

    async def _async_update_data(self):
        """Update the current weather and forecasts."""
        try:
            return await self.client.get_weather_data(
                self.config_entry.data[CONF_LOCATION][CONF_LATITUDE],
                self.config_entry.data[CONF_LOCATION][CONF_LONGITUDE],
                ["currentWeather", "forecastDaily", "forecastHourly"],
            )
        except WeatherKitApiClientAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except WeatherKitApiClientError as exception:
            raise UpdateFailed(exception) from exception
