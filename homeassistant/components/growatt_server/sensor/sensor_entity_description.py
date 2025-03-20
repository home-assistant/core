"""Sensor Entity Description for the Growatt integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntityDescription


@dataclass(frozen=True)
class GrowattRequiredKeysMixin:
    """Mixin for required keys."""

    api_key: str


@dataclass(frozen=True)
class GrowattSensorEntityDescription(SensorEntityDescription, GrowattRequiredKeysMixin):
    """Describes Growatt sensor entity."""

    precision: int | None = None
    currency: bool = False
    previous_value_drop_threshold: float | None = None
    never_resets: bool = False
