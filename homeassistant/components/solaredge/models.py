"""Models for the SolarEdge integration."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntityDescription


@dataclass
class SolarEdgeSensorEntityRequiredKeyMixin:
    """Sensor entity description with json_key for SolarEdge."""

    json_key: str


@dataclass
class SolarEdgeSensorEntityDescription(
    SensorEntityDescription, SolarEdgeSensorEntityRequiredKeyMixin
):
    """Sensor entity description for SolarEdge."""
