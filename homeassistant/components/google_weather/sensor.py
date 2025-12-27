"""Support for Google Weather sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from google_weather_api import CurrentConditionsResponse, DailyForecastResponse

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    UV_INDEX,
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfVolumetricFlux,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import (
    GoogleWeatherConfigEntry,
    GoogleWeatherCurrentConditionsCoordinator,
    GoogleWeatherDailyForecastCoordinator,
)
from .entity import GoogleWeatherBaseEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class GoogleWeatherSensorDescription(SensorEntityDescription):
    """Class describing Google Weather sensor entities."""

    value_fn: Callable[[CurrentConditionsResponse], str | int | float | None]


@dataclass(frozen=True, kw_only=True)
class GoogleWeatherDailyForecastSensorDescription(SensorEntityDescription):
    """Class describing Google Weather daily forecast sensor entities."""

    value_fn: Callable[[DailyForecastResponse], float | None]


SENSOR_TYPES: tuple[GoogleWeatherSensorDescription, ...] = (
    GoogleWeatherSensorDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: data.temperature.degrees,
    ),
    GoogleWeatherSensorDescription(
        key="feelsLikeTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: data.feels_like_temperature.degrees,
        translation_key="apparent_temperature",
    ),
    GoogleWeatherSensorDescription(
        key="dewPoint",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: data.dew_point.degrees,
        translation_key="dew_point",
    ),
    GoogleWeatherSensorDescription(
        key="heatIndex",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: data.heat_index.degrees,
        translation_key="heat_index",
    ),
    GoogleWeatherSensorDescription(
        key="windChill",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: data.wind_chill.degrees,
        translation_key="wind_chill",
    ),
    GoogleWeatherSensorDescription(
        key="relativeHumidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: data.relative_humidity,
    ),
    GoogleWeatherSensorDescription(
        key="uvIndex",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UV_INDEX,
        value_fn=lambda data: data.uv_index,
        translation_key="uv_index",
    ),
    GoogleWeatherSensorDescription(
        key="precipitation_probability",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: data.precipitation.probability.percent,
        translation_key="precipitation_probability",
    ),
    GoogleWeatherSensorDescription(
        key="precipitation_qpf",
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        value_fn=lambda data: data.precipitation.qpf.quantity,
    ),
    GoogleWeatherSensorDescription(
        key="thunderstormProbability",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: data.thunderstorm_probability,
        translation_key="thunderstorm_probability",
    ),
    GoogleWeatherSensorDescription(
        key="airPressure",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        native_unit_of_measurement=UnitOfPressure.HPA,
        value_fn=lambda data: data.air_pressure.mean_sea_level_millibars,
    ),
    GoogleWeatherSensorDescription(
        key="wind_direction",
        device_class=SensorDeviceClass.WIND_DIRECTION,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT_ANGLE,
        native_unit_of_measurement=DEGREE,
        value_fn=lambda data: data.wind.direction.degrees,
    ),
    GoogleWeatherSensorDescription(
        key="wind_speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        value_fn=lambda data: data.wind.speed.value,
    ),
    GoogleWeatherSensorDescription(
        key="wind_gust",
        device_class=SensorDeviceClass.WIND_SPEED,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        value_fn=lambda data: data.wind.gust.value,
        translation_key="wind_gust_speed",
    ),
    GoogleWeatherSensorDescription(
        key="visibility",
        device_class=SensorDeviceClass.DISTANCE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        value_fn=lambda data: data.visibility.distance,
        translation_key="visibility",
    ),
    GoogleWeatherSensorDescription(
        key="cloudCover",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: data.cloud_cover,
        translation_key="cloud_coverage",
    ),
    GoogleWeatherSensorDescription(
        key="weatherCondition",
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.weather_condition.description.text,
        translation_key="weather_condition",
    ),
)


DAILY_FORECAST_SENSOR_TYPES: tuple[GoogleWeatherDailyForecastSensorDescription, ...] = (
    GoogleWeatherDailyForecastSensorDescription(
        key="daily_max_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: (
            data.forecast_days[0].max_temperature.degrees
            if data.forecast_days
            else None
        ),
        translation_key="daily_max_temperature",
    ),
    GoogleWeatherDailyForecastSensorDescription(
        key="daily_min_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: (
            data.forecast_days[0].min_temperature.degrees
            if data.forecast_days
            else None
        ),
        translation_key="daily_min_temperature",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GoogleWeatherConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add Google Weather entities from a config_entry."""
    for subentry in entry.subentries.values():
        subentry_runtime_data = entry.runtime_data.subentries_runtime_data[
            subentry.subentry_id
        ]
        observation_coordinator = subentry_runtime_data.coordinator_observation
        daily_forecast_coordinator = subentry_runtime_data.coordinator_daily_forecast

        entities: list[GoogleWeatherSensor | GoogleWeatherDailyForecastSensor] = [
            GoogleWeatherSensor(observation_coordinator, subentry, description)
            for description in SENSOR_TYPES
            if description.value_fn(observation_coordinator.data) is not None
        ]
        entities.extend(
            GoogleWeatherDailyForecastSensor(
                daily_forecast_coordinator, subentry, description
            )
            for description in DAILY_FORECAST_SENSOR_TYPES
            if description.value_fn(daily_forecast_coordinator.data) is not None
        )
        async_add_entities(entities, config_subentry_id=subentry.subentry_id)


class GoogleWeatherSensor(
    CoordinatorEntity[GoogleWeatherCurrentConditionsCoordinator],
    GoogleWeatherBaseEntity,
    SensorEntity,
):
    """Define a Google Weather entity."""

    entity_description: GoogleWeatherSensorDescription

    def __init__(
        self,
        coordinator: GoogleWeatherCurrentConditionsCoordinator,
        subentry: ConfigSubentry,
        description: GoogleWeatherSensorDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        GoogleWeatherBaseEntity.__init__(
            self, coordinator.config_entry, subentry, description.key
        )
        self.entity_description = description

    @property
    def native_value(self) -> str | int | float | None:
        """Return the state."""
        return self.entity_description.value_fn(self.coordinator.data)


class GoogleWeatherDailyForecastSensor(
    CoordinatorEntity[GoogleWeatherDailyForecastCoordinator],
    GoogleWeatherBaseEntity,
    SensorEntity,
):
    """Define a Google Weather daily forecast sensor entity."""

    entity_description: GoogleWeatherDailyForecastSensorDescription

    def __init__(
        self,
        coordinator: GoogleWeatherDailyForecastCoordinator,
        subentry: ConfigSubentry,
        description: GoogleWeatherDailyForecastSensorDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        GoogleWeatherBaseEntity.__init__(
            self, coordinator.config_entry, subentry, description.key
        )
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        """Return the state."""
        return self.entity_description.value_fn(self.coordinator.data)
