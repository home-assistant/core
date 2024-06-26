"""The Tessie integration models."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.helpers.device_registry import DeviceInfo

from .coordinator import TessieStateUpdateCoordinator


@dataclass
class TessieData:
    """Data for the Tessie integration."""

    vehicles: list[TessieVehicleData]


@dataclass
class TessieVehicleData:
    """Data for a Tessie vehicle."""

    data_coordinator: TessieStateUpdateCoordinator
    device: DeviceInfo
    vin: str
