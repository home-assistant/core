"""Definitions for OpenEVSE sensors added to MQTT."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTime,
)

from .const import STATES


def status_transform(value):
    """Transform 'state' value into a descriptive string."""
    return STATES[int(value)]


@dataclass
class OpenEVSESensorEntityDescription(SensorEntityDescription):
    """Sensor entity description for OpenEVSE."""

    state: Callable | None = None
    topic: str | None = None  # If not provided, assume key is topic


SENSORS: tuple[OpenEVSESensorEntityDescription, ...] = (
    OpenEVSESensorEntityDescription(
        key="amp",
        translation_key="current",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OpenEVSESensorEntityDescription(
        key="voltage",
        translation_key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OpenEVSESensorEntityDescription(
        key="power",
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OpenEVSESensorEntityDescription(
        key="session_elapsed",
        translation_key="session_elapsed",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    OpenEVSESensorEntityDescription(
        key="session_energy",
        translation_key="session_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    OpenEVSESensorEntityDescription(
        key="status",
        translation_key="status",
        topic="state",
        icon="mdi:information-outline",
        state=status_transform,
    ),
    OpenEVSESensorEntityDescription(
        key="total_energy",
        translation_key="total_energy",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
)
