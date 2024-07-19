"""The Tesla Fleet integration models."""

from __future__ import annotations

from dataclasses import dataclass

from tesla_fleet_api import EnergySpecific, VehicleSpecific
from tesla_fleet_api.const import Scope

from homeassistant.helpers.device_registry import DeviceInfo

from .coordinator import (
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

    api: VehicleSpecific
    coordinator: TeslaFleetVehicleDataCoordinator
    vin: str
    device: DeviceInfo


@dataclass
class TeslaFleetEnergyData:
    """Data for a vehicle in the TeslaFleet integration."""

    api: EnergySpecific
    live_coordinator: TeslaFleetEnergySiteLiveCoordinator
    info_coordinator: TeslaFleetEnergySiteInfoCoordinator
    id: int
    device: DeviceInfo
