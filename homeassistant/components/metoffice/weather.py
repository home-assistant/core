"""Support for UK Met Office weather service."""
from __future__ import annotations

from typing import Any

from datapoint.Timestep import Timestep

from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
    Forecast,
    WeatherEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import TEMP_CELSIUS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import get_device_info
from .const import (
    ATTRIBUTION,
    CONDITION_CLASSES,
    DEFAULT_NAME,
    DOMAIN,
    METOFFICE_COORDINATES,
    METOFFICE_DAILY_COORDINATOR,
    METOFFICE_HOURLY_COORDINATOR,
    METOFFICE_NAME,
    MODE_3HOURLY_LABEL,
    MODE_DAILY,
    MODE_DAILY_LABEL,
    VISIBILITY_CLASSES,
    VISIBILITY_DISTANCE_CLASSES,
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
        data[ATTR_FORECAST_CONDITION] = _get_weather_condition(timestep.weather.value)
    if timestep.precipitation:
        data[ATTR_FORECAST_PRECIPITATION_PROBABILITY] = timestep.precipitation.value
    if timestep.temperature:
        data[ATTR_FORECAST_TEMP] = timestep.temperature.value
    if timestep.wind_direction:
        data[ATTR_FORECAST_WIND_BEARING] = timestep.wind_direction.value
    if timestep.wind_speed:
        data[ATTR_FORECAST_WIND_SPEED] = timestep.wind_speed.value
    return data


def _get_weather_condition(metoffice_code: str) -> str | None:
    for hass_name, metoffice_codes in CONDITION_CLASSES.items():
        if metoffice_code in metoffice_codes:
            return hass_name
    return None


class MetOfficeWeather(CoordinatorEntity[MetOfficeData], WeatherEntity):
    """Implementation of a Met Office weather condition."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[MetOfficeData],
        hass_data: dict[str, Any],
        use_3hourly: bool,
    ) -> None:
        """Initialise the platform with a data instance."""
        super().__init__(coordinator)

        mode_label = MODE_3HOURLY_LABEL if use_3hourly else MODE_DAILY_LABEL
        self._attr_device_info = get_device_info(
            coordinates=hass_data[METOFFICE_COORDINATES], name=hass_data[METOFFICE_NAME]
        )
        self._attr_name = f"{DEFAULT_NAME} {hass_data[METOFFICE_NAME]} {mode_label}"
        self._attr_unique_id = hass_data[METOFFICE_COORDINATES]
        if not use_3hourly:
            self._attr_unique_id = f"{self._attr_unique_id}_{MODE_DAILY}"

    @property
    def condition(self) -> str | None:
        """Return the current condition."""
        if self.coordinator.data.now:
            return _get_weather_condition(self.coordinator.data.now.weather.value)
        return None

    @property
    def temperature(self) -> float | None:
        """Return the platform temperature."""
        if self.coordinator.data.now.temperature:
            return self.coordinator.data.now.temperature.value
        return None

    @property
    def temperature_unit(self) -> str:
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def visibility(self):
        """Return the platform visibility."""
        _visibility = None
        weather_now = self.coordinator.data.now
        if hasattr(weather_now, "visibility"):
            visibility_class = VISIBILITY_CLASSES.get(weather_now.visibility.value)
            visibility_distance = VISIBILITY_DISTANCE_CLASSES.get(
                weather_now.visibility.value
            )
            _visibility = f"{visibility_class} - {visibility_distance}"
        return _visibility

    @property
    def pressure(self) -> float | None:
        """Return the mean sea-level pressure."""
        weather_now = self.coordinator.data.now
        if weather_now and weather_now.pressure:
            return weather_now.pressure.value
        return None

    @property
    def humidity(self) -> float | None:
        """Return the relative humidity."""
        weather_now = self.coordinator.data.now
        if weather_now and weather_now.humidity:
            return weather_now.humidity.value
        return None

    @property
    def wind_speed(self) -> float | None:
        """Return the wind speed."""
        weather_now = self.coordinator.data.now
        if weather_now and weather_now.wind_speed:
            return weather_now.wind_speed.value
        return None

    @property
    def wind_bearing(self) -> str | None:
        """Return the wind bearing."""
        weather_now = self.coordinator.data.now
        if weather_now and weather_now.wind_direction:
            return weather_now.wind_direction.value
        return None

    @property
    def forecast(self) -> list[Forecast] | None:
        """Return the forecast array."""
        if self.coordinator.data.forecast is None:
            return None
        return [
            _build_forecast_data(timestep)
            for timestep in self.coordinator.data.forecast
        ]

    @property
    def attribution(self) -> str:
        """Return the attribution."""
        return ATTRIBUTION
