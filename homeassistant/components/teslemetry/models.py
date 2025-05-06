"""The Teslemetry integration models."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass

from tesla_fleet_api.const import Scope
from tesla_fleet_api.teslemetry import EnergySite, Vehicle
from teslemetry_stream import TeslemetryStream, TeslemetryStreamVehicle

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

    unique_id: str
    vehicles: list[TeslemetryVehicleData]
    energysites: list[TeslemetryEnergyData]
    scopes: list[Scope]


@dataclass
class TeslemetryVehicleData:
    """Data for a vehicle in the Teslemetry integration."""

    api: Vehicle
    config_entry: ConfigEntry
    coordinator: TeslemetryVehicleDataCoordinator
    poll: bool
    stream: TeslemetryStream
    stream_vehicle: TeslemetryStreamVehicle
    vin: str
    firmware: str
    device: DeviceInfo
    remove_listener: Callable
    wakelock = asyncio.Lock()


@dataclass
class TeslemetryEnergyData:
    """Data for a vehicle in the Teslemetry integration."""

    api: EnergySite
    live_coordinator: TeslemetryEnergySiteLiveCoordinator | None
    info_coordinator: TeslemetryEnergySiteInfoCoordinator
    history_coordinator: TeslemetryEnergyHistoryCoordinator | None
    id: int
    device: DeviceInfo
