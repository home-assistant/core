"""Sensor descriptions for Rointe."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import ENERGY_KILO_WATT_HOUR, POWER_WATT, TEMP_CELSIUS
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.typing import StateType

from .device_manager import RointeDevice


@dataclass
class RointeSensorEntityDescriptionMixin:
    """Define a description mixin for Rointe sensor entities."""

    value_fn: Callable[[RointeDevice], StateType]
    last_reset_fn: Callable[[RointeDevice], datetime | None]


@dataclass
class RointeSensorEntityDescription(
    SensorEntityDescription, RointeSensorEntityDescriptionMixin
):
    """Define an object to describe Rointe sensor entities."""


SENSOR_DESCRIPTIONS = [
    # Current room temperature sensor (probe value).
    RointeSensorEntityDescription(
        key="current_temperature",
        name="Current Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda radiator: radiator.temp_probe,
        last_reset_fn=lambda radiator: None,
    ),
    # Energy usage in Kw/h.
    RointeSensorEntityDescription(
        key="energy",
        name="Energy Consumption",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda radiator: radiator.energy_data.kwh
        if radiator.energy_data
        else None,
        last_reset_fn=lambda radiator: radiator.energy_data.start
        if radiator.energy_data
        else None,
    ),
    # Effective power usage in W.
    RointeSensorEntityDescription(
        key="power",
        name="Effective Power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=POWER_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda radiator: radiator.energy_data.effective_power
        if radiator.energy_data
        else None,
        last_reset_fn=lambda radiator: None,
    ),
]
