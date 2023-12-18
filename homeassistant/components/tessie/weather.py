"""Weather platform for Tessie integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
from http import HTTPStatus
import logging
from typing import Any

from aiohttp import ClientResponseError
from tessie_api import get_weather

from homeassistant.components.weather import WeatherEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN
from .coordinator import TessieDataUpdateCoordinator
from .entity import TessieEntity

_LOGGER = logging.getLogger(__name__)

TESSIE_WEATHER_SYNC_INTERVAL = 300


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Tessie Weather platform from a config entry."""
    coordinators = hass.data[DOMAIN][entry.entry_id]

    weathercoordinators = (
        TessieWeatherDataCoordinator(hass, coordinator.api_key, coordinator.vin)
        for coordinator in coordinators
    )

    tasks = (
        weathercoordinator.async_refresh() for weathercoordinator in weathercoordinators
    )
    await asyncio.gather(*tasks)

    async_add_entities(
        TessieWeatherEntity(coordinator, weathercoordinator)
        for coordinator, weathercoordinator in zip(coordinators, weathercoordinators)
    )


class TessieWeatherDataCoordinator(DataUpdateCoordinator):
    """Data Update Coordinator for Weather."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_key: str,
        vin: str,
    ) -> None:
        """Initialize Tessie Weather Data Update Coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Tessie Weather",
            update_method=self.async_update_data,
            update_interval=timedelta(seconds=TESSIE_WEATHER_SYNC_INTERVAL),
        )
        self.api_key = api_key
        self.vin = vin
        self.session = async_get_clientsession(hass)

    async def async_update_data(self) -> dict[str, Any]:
        """Update weather data using Tessie API."""

        try:
            return await get_weather(
                session=self.session,
                api_key=self.api_key,
                vin=self.vin,
            )
        except ClientResponseError as e:
            if e.status == HTTPStatus.UNAUTHORIZED:
                # Auth Token is no longer valid
                raise ConfigEntryAuthFailed from e
            raise e


class TessieWeatherEntity(TessieEntity, WeatherEntity):
    """Base class for Tessie metric Weathers."""

    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_precipitation_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.KILOMETERS_PER_HOUR
    _attr_native_visibility_unit = UnitOfLength.METERS

    def __init__(
        self,
        vehiclecoordinator: TessieDataUpdateCoordinator,
        weathercoordinator: TessieWeatherDataCoordinator,
    ) -> None:
        """Initialize the sensor."""
        # Setup base data
        super().__init__(vehiclecoordinator, "weather")
        # Setup CoordinatorEntity with weathercoordinator instead.
        CoordinatorEntity.__init__(self, weathercoordinator)
        self.weathercoordinator = weathercoordinator

    @property
    def native_apparent_temperature(self) -> float | None:
        """Return the apparent temperature in native units."""
        return self.weathercoordinator.data.get("feels_like")

    @property
    def native_temperature(self) -> float | None:
        """Return the temperature in native units."""
        return self.weathercoordinator.data.get("temperature")

    @property
    def native_pressure(self) -> float | None:
        """Return the pressure in native units."""
        return self.weathercoordinator.data.get("pressure")

    @property
    def humidity(self) -> float | None:
        """Return the humidity in native units."""
        return self.weathercoordinator.data.get("humidity")

    @property
    def native_wind_speed(self) -> float | None:
        """Return the wind speed in native units."""
        return self.weathercoordinator.data.get("wind_speed")

    @property
    def wind_bearing(self) -> float | str | None:
        """Return the wind bearing."""
        return self.weathercoordinator.data.get("wind_direction")

    @property
    def cloud_coverage(self) -> float | None:
        """Return the Cloud coverage in %."""
        return self.weathercoordinator.data.get("cloudiness")

    @property
    def native_visibility(self) -> float | None:
        """Return the visibility in native units."""
        return self.weathercoordinator.data.get("visibility")

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        return self.weathercoordinator.data.get("condition")
