"""Support for Google Weather sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import (
    GoogleWeatherConfigEntry,
    GoogleWeatherCurrentConditionsCoordinator,
)
from .entity import GoogleWeatherBaseEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class GoogleWeatherSensorDescription(SensorEntityDescription):
    """Class describing Google Weather sensor entities."""

    value_fn: Callable[[dict[str, Any]], str | int | float | None]


SENSOR_TYPES: tuple[GoogleWeatherSensorDescription, ...] = (
    GoogleWeatherSensorDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=True,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: cast(float, data["temperature"]["degrees"]),
        translation_key="temperature",
    ),
    GoogleWeatherSensorDescription(
        key="feelsLikeTemperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=True,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: cast(float, data["feelsLikeTemperature"]["degrees"]),
        translation_key="apparent_temperature",
    ),
    GoogleWeatherSensorDescription(
        key="dewPoint",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: cast(float, data["dewPoint"]["degrees"]),
        translation_key="dew_point",
    ),
    GoogleWeatherSensorDescription(
        key="heatIndex",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: cast(float, data["heatIndex"]["degrees"]),
        translation_key="heat_index",
    ),
    GoogleWeatherSensorDescription(
        key="windChill",
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        value_fn=lambda data: cast(float, data["windChill"]["degrees"]),
        translation_key="wind_chill",
    ),
    GoogleWeatherSensorDescription(
        key="relativeHumidity",
        device_class=SensorDeviceClass.HUMIDITY,
        entity_registry_enabled_default=True,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: cast(int, data["relativeHumidity"]),
        translation_key="humidity",
    ),
    GoogleWeatherSensorDescription(
        key="uvIndex",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UV_INDEX,
        value_fn=lambda data: cast(int, data["uvIndex"]),
        translation_key="uv_index",
    ),
    GoogleWeatherSensorDescription(
        key="precipitation_probability",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: cast(
            int, data["precipitation"]["probability"]["percent"]
        ),
        translation_key="precipitation_probability",
    ),
    GoogleWeatherSensorDescription(
        key="precipitation_qpf",
        device_class=SensorDeviceClass.PRECIPITATION_INTENSITY,
        entity_registry_enabled_default=True,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfVolumetricFlux.MILLIMETERS_PER_HOUR,
        value_fn=lambda data: cast(float, data["precipitation"]["qpf"]["quantity"]),
        translation_key="precipitation_qpf",
    ),
    GoogleWeatherSensorDescription(
        key="thunderstormProbability",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: cast(int, data["thunderstormProbability"]),
        translation_key="thunderstorm_probability",
    ),
    GoogleWeatherSensorDescription(
        key="airPressure",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        native_unit_of_measurement=UnitOfPressure.HPA,
        value_fn=lambda data: cast(float, data["airPressure"]["meanSeaLevelMillibars"]),
        translation_key="pressure",
    ),
    GoogleWeatherSensorDescription(
        key="wind_direction",
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=DEGREE,
        value_fn=lambda data: cast(int, data["wind"]["direction"]["degrees"]),
        translation_key="wind_direction",
    ),
    GoogleWeatherSensorDescription(
        key="wind_speed",
        device_class=SensorDeviceClass.WIND_SPEED,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        value_fn=lambda data: cast(float, data["wind"]["speed"]["value"]),
        translation_key="wind_speed",
    ),
    GoogleWeatherSensorDescription(
        key="wind_gust",
        device_class=SensorDeviceClass.WIND_SPEED,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        value_fn=lambda data: cast(float, data["wind"]["gust"]["value"]),
        translation_key="wind_gust_speed",
    ),
    GoogleWeatherSensorDescription(
        key="visibility",
        device_class=SensorDeviceClass.DISTANCE,
        entity_registry_enabled_default=False,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfLength.KILOMETERS,
        value_fn=lambda data: cast(float, data["visibility"]["distance"]),
        translation_key="visibility",
    ),
    GoogleWeatherSensorDescription(
        key="cloudCover",
        entity_registry_enabled_default=True,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        value_fn=lambda data: cast(int, data["cloudCover"]),
        translation_key="cloud_coverage",
    ),
    GoogleWeatherSensorDescription(
        key="weatherCondition",
        entity_registry_enabled_default=False,
        value_fn=lambda data: cast(
            str, data["weatherCondition"]["description"]["text"]
        ),
        translation_key="weather_condition",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GoogleWeatherConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add Google Weather entities from a config_entry."""
    coordinator: GoogleWeatherCurrentConditionsCoordinator = (
        entry.runtime_data.coordinator_observation
    )

    sensors = [
        GoogleWeatherSensor(coordinator, description)
        for description in SENSOR_TYPES
        if description.value_fn(coordinator.data) is not None
    ]

    async_add_entities(sensors)


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
        description: GoogleWeatherSensorDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        GoogleWeatherBaseEntity.__init__(
            self, coordinator.config_entry, description.key
        )
        self.entity_description = description

    @property
    def native_value(self) -> str | int | float | None:
        """Return the state."""
        return self.entity_description.value_fn(self.coordinator.data)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data update."""
        self.async_write_ha_state()
