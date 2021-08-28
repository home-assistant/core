"""Models for the AVM FRITZ!SmartHome integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, TypedDict

from pyfritzhome import FritzhomeDevice

from homeassistant.components.binary_sensor import BinarySensorEntityDescription
from homeassistant.components.sensor import SensorEntityDescription


class EntityInfo(TypedDict):
    """TypedDict for EntityInfo."""

    name: str
    entity_id: str
    unit_of_measurement: str | None
    device_class: str | None
    state_class: str | None


class FritzExtraAttributes(TypedDict):
    """TypedDict for sensors extra attributes."""

    device_locked: bool
    locked: bool


class ClimateExtraAttributes(FritzExtraAttributes, total=False):
    """TypedDict for climates extra attributes."""

    battery_low: bool
    battery_level: int
    holiday_mode: bool
    summer_mode: bool
    window_open: bool


class SwitchExtraAttributes(TypedDict, total=False):
    """TypedDict for sensors extra attributes."""

    device_locked: bool
    locked: bool
    total_consumption: str
    total_consumption_unit: str
    temperature: str
    temperature_unit: str


@dataclass
class FritzEntityDescriptionMixinBase:
    """Bases description mixin for Fritz!Smarthome entities."""

    suitable: Callable[[FritzhomeDevice], bool]


@dataclass
class FritzEntityDescriptionMixinSensor(FritzEntityDescriptionMixinBase):
    """Sensor description mixin for Fritz!Smarthome entities."""

    native_value: Callable[[FritzhomeDevice], float | int | None]


@dataclass
class FritzEntityDescriptionMixinBinarySensor(FritzEntityDescriptionMixinBase):
    """BinarySensor description mixin for Fritz!Smarthome entities."""

    is_on: Callable[[FritzhomeDevice], bool | None]


@dataclass
class FritzSensorEntityDescription(
    SensorEntityDescription, FritzEntityDescriptionMixinSensor
):
    """Description for Fritz!Smarthome sensor entities."""


@dataclass
class FritzBinarySensorEntityDescription(
    BinarySensorEntityDescription, FritzEntityDescriptionMixinBinarySensor
):
    """Description for Fritz!Smarthome binary sensor entities."""
