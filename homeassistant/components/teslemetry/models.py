"""The Teslemetry integration models."""
from __future__ import annotations

from dataclasses import dataclass

from tesla_fleet_api import Teslemetry
from teslemetry_stream import TeslemetryStream

@dataclass
class TeslemetryData:
    """Data for the Teslemetry integration."""

    api: Teslemetry.Vehicle.Specific
    stream: TeslemetryStream
    fields: dict[str, str] = {}
