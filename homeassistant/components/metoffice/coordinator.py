"""Data update coordinator for the Met Office integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Literal

from datapoint.exceptions import APIException
from datapoint.Forecast import Forecast
from datapoint.Manager import Manager
from requests import HTTPError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    TimestampDataUpdateCoordinator,
    UpdateFailed,
)

from .const import DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type MetOfficeConfigEntry = ConfigEntry[MetOfficeRuntimeData]


@dataclass
class MetOfficeRuntimeData:
    """Met Office config entry."""

    coordinates: str
    hourly_coordinator: MetOfficeUpdateCoordinator
    daily_coordinator: MetOfficeUpdateCoordinator
    twice_daily_coordinator: MetOfficeUpdateCoordinator
    name: str


class MetOfficeUpdateCoordinator(TimestampDataUpdateCoordinator[Forecast]):
    """Coordinator for Met Office forecast data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        name: str,
        connection: Manager,
        latitude: float,
        longitude: float,
        frequency: Literal["daily", "twice-daily", "hourly"],
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            config_entry=entry,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self._connection = connection
        self._latitude = latitude
        self._longitude = longitude
        self._frequency = frequency

    async def _async_update_data(self) -> Forecast:
        """Get data from Met Office."""
        return await self.hass.async_add_executor_job(
            fetch_data,
            self._connection,
            self._latitude,
            self._longitude,
            self._frequency,
        )


def fetch_data(
    connection: Manager,
    latitude: float,
    longitude: float,
    frequency: Literal["daily", "twice-daily", "hourly"],
) -> Forecast:
    """Fetch weather and forecast from Datapoint API."""
    try:
        return connection.get_forecast(
            latitude, longitude, frequency, convert_weather_code=False
        )
    except (ValueError, APIException) as err:
        _LOGGER.error("Check Met Office connection: %s", err.args)
        raise UpdateFailed from err
    except HTTPError as err:
        if err.response.status_code == 401:
            raise ConfigEntryAuthFailed from err
        raise
