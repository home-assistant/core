"""Models for the AVM FRITZ!SmartHome integration."""
from __future__ import annotations

from typing import TypedDict


class EntityInfo(TypedDict):
    """TypedDict for EntityInfo."""

    name: str
    entity_id: str
    unit_of_measurement: str | None
    device_class: str | None


class ClimateExtraAttributes(TypedDict, total=False):
    """TypedDict for climates extra attributes."""

    battery_low: bool
    device_locked: bool
    locked: bool
    battery_level: int
    holiday_mode: bool
    summer_mode: bool
    window_open: bool


class SensorExtraAttributes(TypedDict):
    """TypedDict for sensors extra attributes."""

    device_locked: bool
    locked: bool


class SwitchExtraAttributes(TypedDict, total=False):
    """TypedDict for sensors extra attributes."""

    device_locked: bool
    locked: bool
    total_consumption: str
    total_consumption_unit: str
    temperature: str
    temperature_unit: str
