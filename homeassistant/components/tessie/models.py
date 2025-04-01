"""The Tessie integration models."""

from __future__ import annotations

from dataclasses import dataclass

from tesla_fleet_api.tessie import EnergySite

from homeassistant.helpers.device_registry import DeviceInfo

from .coordinator import (
    TessieEnergySiteInfoCoordinator,
    TessieEnergySiteLiveCoordinator,
    TessieStateUpdateCoordinator,
)


@dataclass
class TessieData:
    """Data for the Tessie integration."""

    vehicles: list[TessieVehicleData]
    energysites: list[TessieEnergyData]


@dataclass
class TessieEnergyData:
    """Data for a Energy Site in the Tessie integration."""

    api: EnergySite
    live_coordinator: TessieEnergySiteLiveCoordinator
    info_coordinator: TessieEnergySiteInfoCoordinator
    id: int
    device: DeviceInfo


@dataclass
class TessieVehicleData:
    """Data for a Tessie vehicle."""

    data_coordinator: TessieStateUpdateCoordinator
    device: DeviceInfo
    vin: str
