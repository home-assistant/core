"""Support for bluetooth sensors."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.helpers.typing import StateType

from .entity import BluetoothDescriptionRequiredKeysMixin
from .update_coordinator import BluetoothCoordinatorEntity


class BluetoothSensorType(Enum):
    """Enum for predefined bluetooth sensor types."""

    PRESSURE = "pressure"
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"
    BATTERY = "battery"
    RSSI = "rssi"


SENSOR_TYPE_TO_DEVICE_CLASS = {
    BluetoothSensorType.PRESSURE: SensorDeviceClass.PRESSURE,
    BluetoothSensorType.TEMPERATURE: SensorDeviceClass.TEMPERATURE,
    BluetoothSensorType.HUMIDITY: SensorDeviceClass.HUMIDITY,
    BluetoothSensorType.BATTERY: SensorDeviceClass.BATTERY,
    BluetoothSensorType.RSSI: SensorDeviceClass.SIGNAL_STRENGTH,
}


@dataclass
class BluetoothSensorRequiredKeysMixin:
    """Mixin for required keys."""

    native_value: StateType | date | datetime | Decimal | None


@dataclass
class BluetoothSensorEntityDescription(
    SensorEntityDescription,
    BluetoothDescriptionRequiredKeysMixin,
    BluetoothSensorRequiredKeysMixin,
):
    """Describes a bluetooth sensor entity."""


class BluetoothSensorEntity(BluetoothCoordinatorEntity, SensorEntity):
    """Representation of a govee ble sensor."""

    entity_description: BluetoothSensorEntityDescription

    @property
    def native_value(self) -> StateType | date | datetime | Decimal | None:
        """Return the native value."""
        return self.entity_description.native_value
