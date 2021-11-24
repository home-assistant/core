"""Sensor Entity Description for the Growatt integration."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntityDescription


@dataclass
class GrowattRequiredKeysMixin:
    """Mixin for required keys."""

    api_key: str


@dataclass
class GrowattSensorEntityDescription(SensorEntityDescription, GrowattRequiredKeysMixin):
    """Describes Growatt sensor entity."""

    precision: int | None = None
    currency: bool = False
