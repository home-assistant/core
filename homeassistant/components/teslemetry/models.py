"""The Teslemetry integration models."""
from __future__ import annotations

from dataclasses import dataclass

from tesla_fleet_api import Teslemetry


@dataclass
class TeslemetryData:
    """Data for the Teslemetry integration."""

    api: Teslemetry.Vehicle.Specific
    stream: dict  # Will be a Stream object
    fields: dict[str, str] = {}
