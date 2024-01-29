"""The Teslemetry integration models."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from tesla_fleet_api import VehicleSpecific

from .coordinator import TeslemetryVehicleDataCoordinator


@dataclass
class TeslemetryVehicleData:
    """Data for a vehicle in the Teslemetry integration."""

    api: VehicleSpecific
    coordinator: TeslemetryVehicleDataCoordinator
    vin: str
    wakelock = asyncio.Lock()
