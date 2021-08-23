"""Models for the AVM FRITZ!SmartHome integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, TypedDict

from pyfritzhome import FritzhomeDevice

from homeassistant.components.binary_sensor import BinarySensorEntityDescription
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.helpers.entity import EntityDescription


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
class FritzEntityDescription(EntityDescription):
    """Description for Fritz!Smarthome entities."""

    suitable: Callable[[FritzhomeDevice], bool] | None = None


@dataclass
class FritzSensorEntityDescription(FritzEntityDescription, SensorEntityDescription):
    """Description for Fritz!Smarthome sensor entities."""

    state: Callable[[FritzhomeDevice], float | int | None] | None = None


@dataclass
class FritzBinarySensorEntityDescription(
    FritzEntityDescription, BinarySensorEntityDescription
):
    """Description for Fritz!Smarthome binary sensor entities."""

    is_on: Callable[[FritzhomeDevice], bool | None] | None = None
