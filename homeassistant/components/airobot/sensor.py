"""Sensor platform for Airobot thermostat."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from pyairobotrest.models import ThermostatStatus

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.util.dt import utcnow
from homeassistant.util.variance import ignore_variance

from . import AirobotConfigEntry
from .entity import AirobotEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class AirobotSensorEntityDescription(SensorEntityDescription):
    """Describes Airobot sensor entity."""

    value_fn: Callable[[ThermostatStatus], StateType | datetime]
    supported_fn: Callable[[ThermostatStatus], bool] = lambda _: True


uptime_to_stable_datetime = ignore_variance(
    lambda value: utcnow().replace(microsecond=0) - timedelta(seconds=value),
    timedelta(minutes=2),
)

SENSOR_TYPES: tuple[AirobotSensorEntityDescription, ...] = (
    AirobotSensorEntityDescription(
        key="air_temperature",
        translation_key="air_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.temp_air,
    ),
    AirobotSensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.hum_air,
    ),
    AirobotSensorEntityDescription(
        key="floor_temperature",
        translation_key="floor_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.temp_floor,
        supported_fn=lambda status: status.has_floor_sensor,
    ),
    AirobotSensorEntityDescription(
        key="co2",
        device_class=SensorDeviceClass.CO2,
        native_unit_of_measurement=CONCENTRATION_PARTS_PER_MILLION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.co2,
        supported_fn=lambda status: status.has_co2_sensor,
    ),
    AirobotSensorEntityDescription(
        key="air_quality_index",
        device_class=SensorDeviceClass.AQI,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda status: status.aqi,
        supported_fn=lambda status: status.has_co2_sensor,
    ),
    AirobotSensorEntityDescription(
        key="heating_uptime",
        translation_key="heating_uptime",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda status: status.heating_uptime,
        entity_registry_enabled_default=False,
    ),
    AirobotSensorEntityDescription(
        key="errors",
        translation_key="errors",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda status: status.errors,
    ),
    AirobotSensorEntityDescription(
        key="device_uptime",
        translation_key="device_uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda status: uptime_to_stable_datetime(status.device_uptime),
        entity_registry_enabled_default=False,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirobotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Airobot sensor platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        AirobotSensor(coordinator, description)
        for description in SENSOR_TYPES
        if description.supported_fn(coordinator.data.status)
    )


class AirobotSensor(AirobotEntity, SensorEntity):
    """Representation of an Airobot sensor."""

    entity_description: AirobotSensorEntityDescription

    def __init__(
        self,
        coordinator,
        description: AirobotSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.status.device_id}_{description.key}"

    @property
    def native_value(self) -> StateType | datetime:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data.status)
