"""Sensor for the zamg integration."""
from __future__ import annotations

from homeassistant.components.weather import WeatherEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, CONF_STATION_ID, DOMAIN, MANUFACTURER_URL
from .coordinator import ZamgDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the ZAMG weather platform."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [ZamgWeather(coordinator, entry.title, entry.data[CONF_STATION_ID])]
    )


class ZamgWeather(CoordinatorEntity, WeatherEntity):
    """Representation of a weather condition."""

    _attr_attribution = ATTRIBUTION

    def __init__(
        self, coordinator: ZamgDataUpdateCoordinator, name: str, station_id: str
    ) -> None:
        """Initialise the platform with a data instance and station name."""
        super().__init__(coordinator)
        self._attr_unique_id = station_id
        self._attr_name = f"ZAMG {name}"
        self.station_id = f"{station_id}"
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, station_id)},
            manufacturer=ATTRIBUTION,
            configuration_url=MANUFACTURER_URL,
            name=coordinator.name,
        )
        # set units of ZAMG API
        self._attr_native_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_native_pressure_unit = UnitOfPressure.HPA
        self._attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND
        self._attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        return None

    @property
    def native_temperature(self) -> float | None:
        """Return the platform temperature."""
        try:
            if (
                value := self.coordinator.data[self.station_id]["TLAM"]["data"]
            ) is not None:
                return float(value)
            if (
                value := self.coordinator.data[self.station_id]["TL"]["data"]
            ) is not None:
                return float(value)
            return None
        except (KeyError, ValueError, TypeError):
            return None

    @property
    def native_pressure(self) -> float | None:
        """Return the pressure."""
        try:
            return float(self.coordinator.data[self.station_id]["P"]["data"])
        except (KeyError, ValueError, TypeError):
            return None

    @property
    def humidity(self) -> float | None:
        """Return the humidity."""
        try:
            return float(self.coordinator.data[self.station_id]["RFAM"]["data"])
        except (KeyError, ValueError, TypeError):
            return None

    @property
    def native_wind_speed(self) -> float | None:
        """Return the wind speed."""
        try:
            if (
                value := self.coordinator.data[self.station_id]["FFAM"]["data"]
            ) is not None:
                return float(value)
            if (
                value := self.coordinator.data[self.station_id]["FFX"]["data"]
            ) is not None:
                return float(value)
            return None
        except (KeyError, ValueError, TypeError):
            return None

    @property
    def wind_bearing(self) -> float | None:
        """Return the wind bearing."""
        try:
            if (
                value := self.coordinator.data[self.station_id]["DD"]["data"]
            ) is not None:
                return float(value)
            if (
                value := self.coordinator.data[self.station_id]["DDX"]["data"]
            ) is not None:
                return float(value)
            return None
        except (KeyError, ValueError, TypeError):
            return None
