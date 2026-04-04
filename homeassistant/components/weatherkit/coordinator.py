"""DataUpdateCoordinator for WeatherKit integration."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from apple_weatherkit import DataSetType
from apple_weatherkit.client import WeatherKitApiClient, WeatherKitApiClientError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, LOGGER

REQUESTED_DATA_SETS = [
    DataSetType.CURRENT_WEATHER,
    DataSetType.DAILY_FORECAST,
    DataSetType.HOURLY_FORECAST,
    DataSetType.WEATHER_ALERTS,
]

STALE_DATA_THRESHOLD = timedelta(hours=1)

HOURLY_FORECAST_DURATION = timedelta(days=7)


class WeatherKitDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    config_entry: ConfigEntry
    supported_data_sets: list[DataSetType] | None = None
    last_updated_at: datetime | None = None

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: WeatherKitApiClient,
    ) -> None:
        """Initialize."""
        self.client = client
        super().__init__(
            hass=hass,
            logger=LOGGER,
            config_entry=config_entry,
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

        if DataSetType.WEATHER_ALERTS in self.supported_data_sets:
            if self.hass.config.country is None:
                LOGGER.debug(
                    "Weather alerts are available but no country is configured; "
                    "skipping weather alerts"
                )
                self.supported_data_sets.remove(DataSetType.WEATHER_ALERTS)

        LOGGER.debug("Supported data sets: %s", self.supported_data_sets)

    async def _async_update_data(self):
        """Update the current weather and forecasts."""
        try:
            if not self.supported_data_sets:
                await self.update_supported_data_sets()

            dt_now = dt_util.utcnow()
            weather_data_kwargs: dict[str, Any] = {
                "hourly_start": dt_now,
                "hourly_end": dt_now + HOURLY_FORECAST_DURATION,
            }
            country_code = self.hass.config.country
            if country_code is not None:
                weather_data_kwargs["country_code"] = country_code

            updated_data = await self.client.get_weather_data(
                self.config_entry.data[CONF_LATITUDE],
                self.config_entry.data[CONF_LONGITUDE],
                self.supported_data_sets,
                **weather_data_kwargs,
            )
        except WeatherKitApiClientError as exception:
            if self.data is None or (
                self.last_updated_at is not None
                and datetime.now() - self.last_updated_at > STALE_DATA_THRESHOLD
            ):
                raise UpdateFailed(exception) from exception

            LOGGER.debug("Using stale data because update failed: %s", exception)
            return self.data
        else:
            self.last_updated_at = datetime.now()
            return updated_data
