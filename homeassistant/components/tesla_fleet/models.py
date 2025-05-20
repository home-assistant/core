"""The Tesla Fleet integration models."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from tesla_fleet_api.const import Scope
from tesla_fleet_api.tesla import EnergySite, VehicleFleet

from homeassistant.helpers.device_registry import DeviceInfo

from .coordinator import (
    TeslaFleetEnergySiteHistoryCoordinator,
    TeslaFleetEnergySiteInfoCoordinator,
    TeslaFleetEnergySiteLiveCoordinator,
    TeslaFleetVehicleDataCoordinator,
)


@dataclass
class TeslaFleetData:
    """Data for the TeslaFleet integration."""

    vehicles: list[TeslaFleetVehicleData]
    energysites: list[TeslaFleetEnergyData]
    scopes: list[Scope]


@dataclass
class TeslaFleetVehicleData:
    """Data for a vehicle in the TeslaFleet integration."""

    api: VehicleFleet
    coordinator: TeslaFleetVehicleDataCoordinator
    vin: str
    device: DeviceInfo
    signing: bool
    wakelock = asyncio.Lock()


@dataclass
class TeslaFleetEnergyData:
    """Data for a vehicle in the TeslaFleet integration."""

    api: EnergySite
    live_coordinator: TeslaFleetEnergySiteLiveCoordinator
    history_coordinator: TeslaFleetEnergySiteHistoryCoordinator
    info_coordinator: TeslaFleetEnergySiteInfoCoordinator
    id: int
    device: DeviceInfo
