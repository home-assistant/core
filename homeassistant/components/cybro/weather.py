"""Support for the Cybro weather."""
from __future__ import annotations

from typing import cast

from cybro import VarType
from sqlalchemy import false, true

from homeassistant.components.weather import WeatherEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_UNIT_SYSTEM_METRIC,
    SPEED_KILOMETERS_PER_HOUR,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    AREA_WEATHER,
    ATTRIBUTION_PLC,
    DEVICE_DESCRIPTION,
    DOMAIN,
    MANUFACTURER,
)
from .coordinator import CybroDataUpdateCoordinator

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Add a User Programmed Weather Station entity from a config_entry."""

    coordinator: CybroDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    var_prefix = f"c{coordinator.data.plc_info.nad}.weather_"
    has_weather: bool = false
    # search for any weather station var and add it into the read list
    if coordinator.data.plc_info.plc_vars.__contains__(f"{var_prefix}temperature"):
        coordinator.data.add_var(f"{var_prefix}temperature", var_type=VarType.INT)
        has_weather = true
    if coordinator.data.plc_info.plc_vars.__contains__(f"{var_prefix}humidity"):
        coordinator.data.add_var(f"{var_prefix}humidity", var_type=VarType.INT)
        has_weather = true
    if coordinator.data.plc_info.plc_vars.__contains__(f"{var_prefix}wind_speed"):
        coordinator.data.add_var(f"{var_prefix}wind_speed", var_type=VarType.INT)
        has_weather = true
    if coordinator.data.plc_info.plc_vars.__contains__(f"{var_prefix}wind_direction"):
        coordinator.data.add_var(f"{var_prefix}wind_direction", var_type=VarType.INT)
        has_weather = true
    if coordinator.data.plc_info.plc_vars.__contains__(f"{var_prefix}pressure"):
        coordinator.data.add_var(f"{var_prefix}pressure", var_type=VarType.INT)
        has_weather = true

    if has_weather:
        async_add_entities([CybroWeatherEntity(var_prefix, coordinator)])


class CybroWeatherEntity(CoordinatorEntity, WeatherEntity):
    """Define an Weather Station entity."""

    coordinator: CybroDataUpdateCoordinator

    def __init__(
        self, var_prefix: str, coordinator: CybroDataUpdateCoordinator
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._unit_system = CONF_UNIT_SYSTEM_METRIC
        self._attr_name = (
            f"User Weather Station connected to c{coordinator.data.plc_info.nad}"
        )
        self._attr_unique_id = var_prefix
        self._attr_temperature_unit = TEMP_CELSIUS
        self._attr_attribution = ATTRIBUTION_PLC
        self._attr_pressure_unit = SPEED_KILOMETERS_PER_HOUR
        self._attr_device_info = DeviceInfo(
            # entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, var_prefix)},
            manufacturer=MANUFACTURER,
            default_name="Cybro PLC weather station",
            suggested_area=AREA_WEATHER,
            model=DEVICE_DESCRIPTION,
        )

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        return ""
        # try:
        #    return [
        #        for k, v in CONDITION_CLASSES.items()
        #        if self.coordinator.data["WeatherIcon"] in v
        #    ][0]
        # except IndexError:
        #    return None

    @property
    def temperature(self) -> float | None:
        """Return the temperature."""
        try:
            return cast(
                float,
                self.coordinator.data.vars[
                    f"{self._attr_unique_id}temperature"
                ].value_float()
                * 0.1,
            )
        except KeyError:
            return None

    @property
    def pressure(self) -> float | None:
        """Return the pressure."""
        try:
            return cast(
                float,
                self.coordinator.data.vars[
                    f"{self._attr_unique_id}pressure"
                ].value_float(),
            )
        except KeyError:
            return None

    @property
    def humidity(self) -> float | None:
        """Return the humidity."""
        try:
            return cast(
                float,
                self.coordinator.data.vars[
                    f"{self._attr_unique_id}humidity"
                ].value_float(),
            )
        except KeyError:
            return None

    @property
    def wind_speed(self) -> float | None:
        """Return the wind speed."""
        try:
            return cast(
                float,
                self.coordinator.data.vars[
                    f"{self._attr_unique_id}wind_speed"
                ].value_float()
                * 0.1,
            )
        except KeyError:
            return None

    @property
    def wind_bearing(self) -> int | None:
        """Return the wind bearing."""
        try:
            return self.coordinator.data.vars[
                f"{self._attr_unique_id}wind_direction"
            ].value_int()
        except KeyError:
            return None
