"""The Teslemetry integration models."""
from __future__ import annotations

from dataclasses import dataclass

from tesla_fleet_api import Teslemetry
from teslemetry_stream import TeslemetryStream

from .coordinator import TeslemetryVehicleDataCoordinator


@dataclass
class TeslemetryVehicleData:
    """Data for a vehicle in the Teslemetry integration."""

    api: Teslemetry.Vehicle.Specific
    coordinator: TeslemetryVehicleDataCoordinator
    stream: TeslemetryStream
