"""DataUpdateCoordinator for WeatherKit integration."""
from __future__ import annotations

from datetime import timedelta

from apple_weatherkit import DataSetType
from apple_weatherkit.client import WeatherKitApiClient, WeatherKitApiClientError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, LOGGER

REQUESTED_DATA_SETS = [
    DataSetType.CURRENT_WEATHER,
    DataSetType.DAILY_FORECAST,
    DataSetType.HOURLY_FORECAST,
]


class WeatherKitDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    config_entry: ConfigEntry
    supported_data_sets: list[DataSetType] | None = None

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
            update_interval=timedelta(minutes=5),
        )

    async def update_supported_data_sets(self):
        """Obtain the supported data sets for this location and store them."""
        supported_data_sets = await self.client.get_availability(
            self.config_entry.data[CONF_LATITUDE],
            self.config_entry.data[CONF_LONGITUDE],
        )

        self.supported_data_sets = [
            data_set
            for data_set in REQUESTED_DATA_SETS
            if data_set in supported_data_sets
        ]

        LOGGER.debug("Supported data sets: %s", self.supported_data_sets)

    async def _async_update_data(self):
        """Update the current weather and forecasts."""
        try:
            if not self.supported_data_sets:
                await self.update_supported_data_sets()

            return await self.client.get_weather_data(
                self.config_entry.data[CONF_LATITUDE],
                self.config_entry.data[CONF_LONGITUDE],
                self.supported_data_sets,
            )
        except WeatherKitApiClientError as exception:
            raise UpdateFailed(exception) from exception
