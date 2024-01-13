"""The Teslemetry integration models."""
from __future__ import annotations

from dataclasses import dataclass

from tesla_fleet_api import Teslemetry

from .coordinator import TeslemetryVehicleDataCoordinator


@dataclass
class TeslemetryVehicleData:
    """Data for a vehicle in the Teslemetry integration."""

    api: Teslemetry.Vehicle.Specific
    coordinator: TeslemetryVehicleDataCoordinator
