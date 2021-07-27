"""Models for the SolarEdge integration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class SolarEdgeSensor:
    """Represents an SolarEdge Sensor."""

    key: str
    name: str

    json_key: str | None = None
    device_class: str | None = None
    entity_registry_enabled_default: bool = True
    icon: str | None = None
    last_reset: datetime | None = None
    state_class: str | None = None
    unit_of_measurement: str | None = None
