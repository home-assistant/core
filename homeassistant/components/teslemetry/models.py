"""The Teslemetry integration models."""

import asyncio
from dataclasses import dataclass, field

from tesla_fleet_api.const import Scope
from tesla_fleet_api.tesla import EnergySiteRouter
from tesla_fleet_api.teslemetry import EnergySite, Vehicle
from teslemetry_stream import TeslemetryStream, TeslemetryStreamVehicle

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo

from .coordinator import (
    TeslemetryEnergyHistoryCoordinator,
    TeslemetryEnergySiteInfoCoordinator,
    TeslemetryEnergySiteLiveCoordinator,
    TeslemetryMetadataCoordinator,
    TeslemetryVehicleDataCoordinator,
)


@dataclass
class TeslemetryData:
    """Data for the Teslemetry integration."""

    vehicles: list[TeslemetryVehicleData]
    energysites: list[TeslemetryEnergyData]
    scopes: list[Scope]
    stream: TeslemetryStream | None
    metadata_coordinator: TeslemetryMetadataCoordinator
    # Bumped each time a credit-state event lands, with the latest state it
    # reported; lets handle_command tell whether the newest credit state seen
    # since a command started is available, and so ignore an InsufficientCredits
    # response that a later availability event has already superseded.
    credits_generation: int = 0
    credits_available: bool = False


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
    wakelock: asyncio.Lock = field(default_factory=asyncio.Lock)


@dataclass
class TeslemetryEnergyData:
    """Data for an energy site in the Teslemetry integration."""

    api: EnergySite | EnergySiteRouter
    live_coordinator: TeslemetryEnergySiteLiveCoordinator | None
    info_coordinator: TeslemetryEnergySiteInfoCoordinator
    history_coordinator: TeslemetryEnergyHistoryCoordinator | None
    id: int
    device: DeviceInfo
    # Only sites with a battery/Powerwall can pair for local TEDAPI control.
    can_local_control: bool
    subentry_id: str | None
