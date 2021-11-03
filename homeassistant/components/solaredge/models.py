"""Models for the SolarEdge integration."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import SensorEntityDescription


@dataclass
class SolarEdgeSensorEntityDescription(SensorEntityDescription):
    """Sensor entity description for SolarEdge."""

    json_key: str | None = None
