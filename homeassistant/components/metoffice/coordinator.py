"""Data update coordinator for the Met Office integration."""

import asyncio
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Literal, override

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
from homeassistant.util import location as location_util

from .const import DEFAULT_SCAN_INTERVAL, UPDATE_MINIMUM_DISTANCE

_LOGGER = logging.getLogger(__name__)

type MetOfficeConfigEntry = ConfigEntry[MetOfficeRuntimeData]


@dataclass
class MetOfficeRuntimeData:
    """Met Office config entry."""

    name: str
    hourly_coordinator: MetOfficeUpdateCoordinator
    daily_coordinator: MetOfficeUpdateCoordinator
    twice_daily_coordinator: MetOfficeUpdateCoordinator

    @property
    def coordinates(self) -> str:
        """Get current coordinates in string form."""
        [current_latitude, current_longitude] = self._current_coordinates
        return f"{current_latitude}_{current_longitude}"

    def __init__(
        self,
        name: str,
        initial_coordinates: tuple[float, float],
        hourly_coordinator: MetOfficeUpdateCoordinator,
        daily_coordinator: MetOfficeUpdateCoordinator,
        twice_daily_coordinator: MetOfficeUpdateCoordinator,
    ) -> None:
        """Initialize the runtime data."""
        self.name = name

        self._initial_coordinates = initial_coordinates
        self._current_coordinates = initial_coordinates

        self.hourly_coordinator = hourly_coordinator
        self.daily_coordinator = daily_coordinator
        self.twice_daily_coordinator = twice_daily_coordinator

    _initial_coordinates: tuple[float, float]
    _current_coordinates: tuple[float, float]

    async def update_coordinates(
        self, latitude: float | None, longitude: float | None
    ) -> None:
        """Updates the coordinates for the weather forecast."""
        if latitude is None and longitude is None:
            # If neither is supplied, return to original location
            [latitude, longitude] = self._initial_coordinates
        elif latitude is None or longitude is None:
            # Otherwise if only one is not supplied, treat as an error
            _LOGGER.error(
                "When updating location, latitude and longitude must both be supplied or both be omitted"
            )
            return

        # Update the location only if we have moved significantly from the previous
        # location. This will limit the number of times the API is queried unless
        # moving extremely quickly.
        [current_latitude, current_longitude] = self._current_coordinates
        distance = location_util.distance(
            current_latitude,
            current_longitude,
            latitude,
            longitude,
        )
        if distance is not None and distance > UPDATE_MINIMUM_DISTANCE:
            self._current_coordinates = (latitude, longitude)
            await asyncio.gather(
                self.daily_coordinator.update_location(latitude, longitude),
                self.twice_daily_coordinator.update_location(latitude, longitude),
                self.hourly_coordinator.update_location(latitude, longitude),
            )


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
        update_interval: timedelta = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            config_entry=entry,
            update_interval=update_interval,
        )
        self._connection = connection
        self._latitude = latitude
        self._longitude = longitude
        self._frequency = frequency

    async def update_location(self, latitude: float, longitude: float) -> None:
        """Update the location for the weather coordinator."""
        self._latitude = latitude
        self._longitude = longitude
        await self.async_request_refresh()

    @override
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
