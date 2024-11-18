"""Sensor Entity Description for the SunWEG integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntityDescription


@dataclass(frozen=True)
class SunWEGRequiredKeysMixin:
    """Mixin for required keys."""

    api_variable_key: str


@dataclass(frozen=True)
class SunWEGSensorEntityDescription(SensorEntityDescription, SunWEGRequiredKeysMixin):
    """Describes SunWEG sensor entity."""

    api_variable_unit: str | None = None
    previous_value_drop_threshold: float | None = None
    never_resets: bool = False
    icon: str | None = None
