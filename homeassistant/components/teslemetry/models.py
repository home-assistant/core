"""The Teslemetry integration models."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

from tesla_fleet_api import VehicleSpecific, EnergySpecific

from .coordinator import (
    TeslemetryVehicleDataCoordinator,
    TeslemetryEnergyDataCoordinator,
)


@dataclass
class TeslemetryVehicleData:
    """Data for a vehicle in the Teslemetry integration."""

    api: VehicleSpecific
    coordinator: TeslemetryVehicleDataCoordinator
    vin: str
    wakelock = asyncio.Lock()


@dataclass
class TeslemetryEnergyData:
    """Data for a vehicle in the Teslemetry integration."""

    api: EnergySpecific
    coordinator: TeslemetryEnergyDataCoordinator
    # site_info: dict[str, str]
