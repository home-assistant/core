"""Models for the DSMR integration."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DSMRSensor:
    """Represents an DSMR Sensor."""

    name: str
    obis_reference: str

    dsmr_versions: set[str] | None = None
    force_update: bool = False
    is_gas: bool = False
