"""The Tessie integration models."""

from __future__ import annotations

from dataclasses import dataclass

from .coordinator import (
    TessieEnergySiteInfoCoordinator,
    TessieEnergySiteLiveCoordinator,
    TessieStateUpdateCoordinator,
)
from tesla_fleet_api import EnergySpecific
from homeassistant.helpers.device_registry import DeviceInfo

@dataclass
class TessieData:
    """Data for the Tessie integration."""

    vehicles: list[TessieStateUpdateCoordinator]
    energy_sites: list[TessieEnergyData]

@dataclass
class TessieEnergyData:
    """Data for a Energy Site in the Tessie integration."""

    api: EnergySpecific
    live_coordinator: TessieEnergySiteLiveCoordinator
    info_coordinator: TessieEnergySiteInfoCoordinator
    id: int
    device: DeviceInfo