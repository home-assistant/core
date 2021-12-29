"""Support for Open-Meteo weather."""
from __future__ import annotations

from open_meteo import Forecast as OpenMeteoForecast

from homeassistant.components.weather import WeatherEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN, WMO_TO_HA_CONDITION_MAP


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Open-Meteo weather entity based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([OpenMeteoWeatherEntity(entry=entry, coordinator=coordinator)])


class OpenMeteoWeatherEntity(CoordinatorEntity, WeatherEntity):
    """Defines an Open-Meteo weather entity."""

    _attr_temperature_unit = TEMP_CELSIUS
    coordinator: DataUpdateCoordinator[OpenMeteoForecast]

    def __init__(
        self, *, entry: ConfigEntry, coordinator: DataUpdateCoordinator
    ) -> None:
        """Initialize Open-Meteo weather entity."""
        super().__init__(coordinator=coordinator)
        self._attr_unique_id = entry.entry_id
        self._attr_name = entry.title

        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer="Open-Meteo",
            name=entry.title,
        )

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        if not self.coordinator.data.current_weather:
            return None
        return WMO_TO_HA_CONDITION_MAP.get(
            self.coordinator.data.current_weather.weather_code
        )

    @property
    def temperature(self) -> float | None:
        """Return the platform temperature."""
        if not self.coordinator.data.current_weather:
            return None
        return self.coordinator.data.current_weather.temperature

    @property
    def wind_speed(self) -> float | None:
        """Return the wind speed."""
        if not self.coordinator.data.current_weather:
            return None
        return self.coordinator.data.current_weather.wind_speed

    @property
    def wind_bearing(self) -> float | str | None:
        """Return the wind bearing."""
        if not self.coordinator.data.current_weather:
            return None
        return self.coordinator.data.current_weather.wind_direction
