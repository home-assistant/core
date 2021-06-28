"""Models for the DSMR integration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class DSMRSensor:
    """Represents an DSMR Sensor."""

    name: str
    obis_reference: str

    device_class: str | None = None
    dsmr_versions: set[str] | None = None
    entity_registry_enabled_default: bool = True
    force_update: bool = False
    icon: str | None = None
    is_gas: bool = False
    last_reset: datetime | None = None
    state_class: str | None = None
