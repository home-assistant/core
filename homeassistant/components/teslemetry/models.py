"""The Teslemetry integration models."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

from tesla_fleet_api import EnergySpecific, VehicleSpecific
from tesla_fleet_api.const import Scope
from teslemetry_stream import TeslemetryStream

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo

from .coordinator import (
    TeslemetryEnergyHistoryCoordinator,
    TeslemetryEnergySiteInfoCoordinator,
    TeslemetryEnergySiteLiveCoordinator,
    TeslemetryVehicleDataCoordinator,
)


@dataclass
class TeslemetryData:
    """Data for the Teslemetry integration."""

    vehicles: list[TeslemetryVehicleData]
    energysites: list[TeslemetryEnergyData]
    scopes: list[Scope]


@dataclass
class TeslemetryVehicleData:
    """Data for a vehicle in the Teslemetry integration."""

    api: VehicleSpecific
    config_entry: ConfigEntry
    coordinator: TeslemetryVehicleDataCoordinator
    stream: TeslemetryStream
    vin: str
    firmware: str
    device: DeviceInfo
    remove_listener: Callable
    wakelock = asyncio.Lock()


@dataclass
class TeslemetryEnergyData:
    """Data for a vehicle in the Teslemetry integration."""

    api: EnergySpecific
    live_coordinator: TeslemetryEnergySiteLiveCoordinator
    info_coordinator: TeslemetryEnergySiteInfoCoordinator
    history_coordinator: TeslemetryEnergyHistoryCoordinator | None
    id: int
    device: DeviceInfo
