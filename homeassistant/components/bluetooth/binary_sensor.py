"""Support for bluetooth binary sensors."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)

from .entity import BluetoothDescriptionRequiredKeysMixin
from .update_coordinator import BluetoothCoordinatorEntity


class BluetoothBinarySensorType(Enum):
    """Enum for predefined bluetooth binary sensor types."""

    MOTION = "motion"
    PROBLEM = "problem"


BINARY_SENSOR_TYPE_TO_DEVICE_CLASS = {
    BluetoothBinarySensorType.MOTION: BinarySensorDeviceClass.MOTION,
    BluetoothBinarySensorType.PROBLEM: BinarySensorDeviceClass.PROBLEM,
}


@dataclass
class BluetoothBinarySensorRequiredKeysMixin:
    """Mixin for required keys."""

    is_on: bool | None


@dataclass
class BluetoothBinarySensorEntityDescription(
    BinarySensorEntityDescription,
    BluetoothDescriptionRequiredKeysMixin,
    BluetoothBinarySensorRequiredKeysMixin,
):
    """Describes a bluetooth sensor entity."""


class BluetoothBinarySensorEntity(BluetoothCoordinatorEntity, BinarySensorEntity):
    """Representation of a govee ble sensor."""

    entity_description: BluetoothBinarySensorEntityDescription

    @property
    def is_on(self) -> bool | None:
        """Return if the sensor is on."""
        return self.entity_description.is_on
