"""Support for UK Met Office weather service."""
from __future__ import annotations

from typing import Any

from datapoint.Timestep import Timestep

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_NATIVE_TEMP,
    ATTR_FORECAST_NATIVE_WIND_SPEED,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_WIND_BEARING,
    Forecast,
    WeatherEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPressure, UnitOfSpeed, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import get_device_info
from .const import (
    ATTRIBUTION,
<<<<<<< HEAD
    CONDITION_MAP,
=======
    CONDITION_CLASSES,
>>>>>>> dde6ce6a996 (Add unit tests)
    DOMAIN,
    METOFFICE_COORDINATES,
    METOFFICE_DAILY_COORDINATOR,
    METOFFICE_HOURLY_COORDINATOR,
    METOFFICE_NAME,
    MODE_DAILY,
)
from .data import MetOfficeData


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Met Office weather sensor platform."""
    hass_data = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            MetOfficeWeather(hass_data[METOFFICE_HOURLY_COORDINATOR], hass_data, True),
            MetOfficeWeather(hass_data[METOFFICE_DAILY_COORDINATOR], hass_data, False),
        ],
        False,
    )


def _build_forecast_data(timestep: Timestep) -> Forecast:
    data = Forecast(datetime=timestep.date.isoformat())
    if timestep.weather:
<<<<<<< HEAD
        data[ATTR_FORECAST_CONDITION] = CONDITION_MAP.get(timestep.weather.value)
=======
        data[ATTR_FORECAST_CONDITION] = _get_weather_condition(timestep.weather.value)
>>>>>>> dde6ce6a996 (Add unit tests)
    if timestep.precipitation:
        data[ATTR_FORECAST_PRECIPITATION_PROBABILITY] = timestep.precipitation.value
    if timestep.temperature:
        data[ATTR_FORECAST_NATIVE_TEMP] = timestep.temperature.value
    if timestep.wind_direction:
        data[ATTR_FORECAST_WIND_BEARING] = timestep.wind_direction.value
    if timestep.wind_speed:
        data[ATTR_FORECAST_NATIVE_WIND_SPEED] = timestep.wind_speed.value
    return data


<<<<<<< HEAD
=======
def _get_weather_condition(metoffice_code: str) -> str | None:
    for hass_name, metoffice_codes in CONDITION_CLASSES.items():
        if metoffice_code in metoffice_codes:
            return hass_name
    return None


>>>>>>> dde6ce6a996 (Add unit tests)
class MetOfficeWeather(
    CoordinatorEntity[DataUpdateCoordinator[MetOfficeData]], WeatherEntity
):
    """Implementation of a Met Office weather condition."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.MILES_PER_HOUR

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[MetOfficeData],
        hass_data: dict[str, Any],
        use_3hourly: bool,
    ) -> None:
        """Initialise the platform with a data instance."""
        super().__init__(coordinator)

        self._attr_device_info = get_device_info(
            coordinates=hass_data[METOFFICE_COORDINATES], name=hass_data[METOFFICE_NAME]
        )
        self._attr_name = "3-Hourly" if use_3hourly else "Daily"
        self._attr_unique_id = hass_data[METOFFICE_COORDINATES]
        if not use_3hourly:
            self._attr_unique_id = f"{self._attr_unique_id}_{MODE_DAILY}"

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        if self.coordinator.data.now:
<<<<<<< HEAD
            return CONDITION_MAP.get(self.coordinator.data.now.weather.value)
=======
            return _get_weather_condition(self.coordinator.data.now.weather.value)
>>>>>>> dde6ce6a996 (Add unit tests)
        return None

    @property
    def native_temperature(self) -> float | None:
        """Return the platform temperature."""
        weather_now = self.coordinator.data.now
        if weather_now.temperature:
            value = weather_now.temperature.value
            return float(value) if value is not None else None
        return None

    @property
    def native_pressure(self) -> float | None:
        """Return the mean sea-level pressure."""
        weather_now = self.coordinator.data.now
        if weather_now and weather_now.pressure:
            value = weather_now.pressure.value
            return float(value) if value is not None else None
        return None

    @property
    def humidity(self) -> float | None:
        """Return the relative humidity."""
        weather_now = self.coordinator.data.now
        if weather_now and weather_now.humidity:
            value = weather_now.humidity.value
            return float(value) if value is not None else None
        return None

    @property
    def native_wind_speed(self) -> float | None:
        """Return the wind speed."""
        weather_now = self.coordinator.data.now
        if weather_now and weather_now.wind_speed:
            value = weather_now.wind_speed.value
            return float(value) if value is not None else None
        return None

    @property
    def wind_bearing(self) -> str | None:
        """Return the wind bearing."""
        weather_now = self.coordinator.data.now
        if weather_now and weather_now.wind_direction:
            value = weather_now.wind_direction.value
            return str(value) if value is not None else None
        return None

    @property
    def forecast(self) -> list[Forecast] | None:
        """Return the forecast array."""
        return [
            _build_forecast_data(timestep)
            for timestep in self.coordinator.data.forecast
        ]
