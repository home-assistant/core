"""Sensor platform for Sensibo integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pysensibo.model import MotionSensor, SensiboDevice

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    ELECTRIC_POTENTIAL_VOLT,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .coordinator import SensiboDataUpdateCoordinator
from .entity import SensiboDeviceBaseEntity, SensiboMotionBaseEntity


@dataclass
class MotionBaseEntityDescriptionMixin:
    """Mixin for required Sensibo base description keys."""

    value_fn: Callable[[MotionSensor], StateType]


@dataclass
class DeviceBaseEntityDescriptionMixin:
    """Mixin for required Sensibo base description keys."""

    value_fn: Callable[[SensiboDevice], StateType]


@dataclass
class SensiboMotionSensorEntityDescription(
    SensorEntityDescription, MotionBaseEntityDescriptionMixin
):
    """Describes Sensibo Motion sensor entity."""


@dataclass
class SensiboDeviceSensorEntityDescription(
    SensorEntityDescription, DeviceBaseEntityDescriptionMixin
):
    """Describes Sensibo Motion sensor entity."""


MOTION_SENSOR_TYPES: tuple[SensiboMotionSensorEntityDescription, ...] = (
    SensiboMotionSensorEntityDescription(
        key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        name="rssi",
        icon="mdi:wifi",
        value_fn=lambda data: data.rssi,
        entity_registry_enabled_default=False,
    ),
    SensiboMotionSensorEntityDescription(
        key="battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        name="Battery Voltage",
        icon="mdi:battery",
        value_fn=lambda data: data.battery_voltage,
    ),
    SensiboMotionSensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        name="Humidity",
        icon="mdi:water",
        value_fn=lambda data: data.humidity,
    ),
    SensiboMotionSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        name="Temperature",
        icon="mdi:thermometer",
        value_fn=lambda data: data.temperature,
    ),
)
PURE_SENSOR_TYPES: tuple[SensiboDeviceSensorEntityDescription, ...] = (
    SensiboDeviceSensorEntityDescription(
        key="pm25",
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        name="PM2.5",
        icon="mdi:air-filter",
        value_fn=lambda data: data.pm25,
    ),
    SensiboDeviceSensorEntityDescription(
        key="pure_sensitivity",
        name="Pure Sensitivity",
        icon="mdi:air-filter",
        value_fn=lambda data: data.pure_sensitivity,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Sensibo sensor platform."""

    coordinator: SensiboDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensiboMotionSensor | SensiboDeviceSensor] = []

    entities.extend(
        SensiboMotionSensor(coordinator, device_id, sensor_id, sensor_data, description)
        for device_id, device_data in coordinator.data.parsed.items()
        for sensor_id, sensor_data in device_data.motion_sensors.items()
        for description in MOTION_SENSOR_TYPES
        if device_data.motion_sensors
    )
    entities.extend(
        SensiboDeviceSensor(coordinator, device_id, description)
        for device_id, device_data in coordinator.data.parsed.items()
        for description in PURE_SENSOR_TYPES
        if device_data.model == "pure"
    )
    async_add_entities(entities)


class SensiboMotionSensor(SensiboMotionBaseEntity, SensorEntity):
    """Representation of a Sensibo Motion Sensor."""

    entity_description: SensiboMotionSensorEntityDescription

    def __init__(
        self,
        coordinator: SensiboDataUpdateCoordinator,
        device_id: str,
        sensor_id: str,
        sensor_data: MotionSensor,
        entity_description: SensiboMotionSensorEntityDescription,
    ) -> None:
        """Initiate Sensibo Motion Sensor."""
        super().__init__(
            coordinator,
            device_id,
            sensor_id,
            sensor_data,
            entity_description.name,
        )
        self.entity_description = entity_description
        self._attr_unique_id = f"{sensor_id}-{entity_description.key}"
        self._attr_name = (
            f"{self.device_data.name} Motion Sensor {entity_description.name}"
        )

    @property
    def native_value(self) -> StateType:
        """Return value of sensor."""
        return self.entity_description.value_fn(self.sensor_data)


class SensiboDeviceSensor(SensiboDeviceBaseEntity, SensorEntity):
    """Representation of a Sensibo Device Sensor."""

    entity_description: SensiboDeviceSensorEntityDescription

    def __init__(
        self,
        coordinator: SensiboDataUpdateCoordinator,
        device_id: str,
        entity_description: SensiboDeviceSensorEntityDescription,
    ) -> None:
        """Initiate Sensibo Device Sensor."""
        super().__init__(
            coordinator,
            device_id,
        )
        self.entity_description = entity_description
        self._attr_unique_id = f"{device_id}-{entity_description.key}"
        self._attr_name = f"{self.device_data.name} {entity_description.name}"

    @property
    def native_value(self) -> StateType:
        """Return value of sensor."""
        return self.entity_description.value_fn(self.device_data)
