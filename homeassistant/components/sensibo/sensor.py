"""Sensor platform for Sensibo integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ELECTRIC_POTENTIAL_VOLT,
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import DOMAIN
from .coordinator import MotionSensor, SensiboDataUpdateCoordinator
from .entity import SensiboMotionBaseEntity


@dataclass
class BaseEntityDescriptionMixin:
    """Mixin for required GitHub base description keys."""

    value_fn: Callable[[MotionSensor], StateType]


@dataclass
class SensiboSensorEntityDescription(
    SensorEntityDescription, BaseEntityDescriptionMixin
):
    """Describes Sensibo Motion sensor entity."""


MOTION_SENSOR_TYPES: tuple[SensiboSensorEntityDescription, ...] = (
    SensiboSensorEntityDescription(
        key="rssi",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        name="rssi",
        icon="mdi:wifi",
        value_fn=lambda data: data.rssi,
    ),
    SensiboSensorEntityDescription(
        key="battery_voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=ELECTRIC_POTENTIAL_VOLT,
        state_class=SensorStateClass.MEASUREMENT,
        name="Battery Voltage",
        icon="mdi:battery",
        value_fn=lambda data: data.battery_voltage,
    ),
    SensiboSensorEntityDescription(
        key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        name="Humidity",
        icon="mdi:water",
        value_fn=lambda data: data.humidity,
    ),
    SensiboSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        name="Temperature",
        icon="mdi:thermometer",
        value_fn=lambda data: data.temperature,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Sensibo sensor platform."""

    coordinator: SensiboDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        SensiboMotionSensor(coordinator, device_id, sensor_id, sensor_data, description)
        for device_id, device_data in coordinator.data.items()
        for sensor_id, sensor_data in device_data["motion_sensors"]
        for description in MOTION_SENSOR_TYPES
        if device_data["motion_sensors"] and sensor_data[sensor_id]
    )


class SensiboMotionSensor(SensiboMotionBaseEntity, SensorEntity):
    """Representation of a Sensibo numbers."""

    entity_description: SensiboSensorEntityDescription

    def __init__(
        self,
        coordinator: SensiboDataUpdateCoordinator,
        device_id: str,
        sensor_id: str,
        sensor_data: MotionSensor,
        entity_description: SensiboSensorEntityDescription,
    ) -> None:
        """Initiate Sensibo Motion Sensor."""
        super().__init__(
            coordinator, device_id, sensor_id, sensor_data, entity_description
        )
        self.entity_description = entity_description

    @property
    def native_value(self) -> StateType:
        """Return value of sensor."""
        return self.entity_description.value_fn(
            self.coordinator.data[self._device_id][self._sensor_id]
        )
