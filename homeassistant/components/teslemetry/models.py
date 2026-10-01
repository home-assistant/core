"""The Teslemetry integration models."""

import asyncio
from dataclasses import dataclass, field
from typing import Any

from tesla_fleet_api import firmware_at_least
from tesla_fleet_api.const import Scope
from tesla_fleet_api.router import VehicleRouter
from tesla_fleet_api.tesla import EnergySiteRouter
from tesla_fleet_api.teslemetry import EnergySite, Vehicle
from teslemetry_stream import TeslemetryStream, TeslemetryStreamVehicle

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.storage import Store

from .const import CHARGE_ON_SOLAR_LOWER_LIMIT_DEFAULT, DOMAIN
from .coordinator import (
    TeslemetryEnergyHistoryCoordinator,
    TeslemetryEnergySiteInfoCoordinator,
    TeslemetryEnergySiteLiveCoordinator,
    TeslemetryMetadataCoordinator,
    TeslemetryVehicleDataCoordinator,
)

STORAGE_VERSION = 1


@dataclass
class TeslemetryData:
    """Data for the Teslemetry integration."""

    vehicles: list[TeslemetryVehicleData]
    energysites: list[TeslemetryEnergyData]
    scopes: list[Scope]
    stream: TeslemetryStream | None
    metadata_coordinator: TeslemetryMetadataCoordinator
    charge_on_solar_store: TeslemetryChargeOnSolarStore


@dataclass
class TeslemetryVehicleData:
    """Data for a vehicle in the Teslemetry integration."""

    api: Vehicle | VehicleRouter
    config_entry: ConfigEntry
    coordinator: TeslemetryVehicleDataCoordinator
    poll: bool
    stream: TeslemetryStream
    stream_vehicle: TeslemetryStreamVehicle
    vin: str
    firmware: str
    device: DeviceInfo
    wakelock: asyncio.Lock = field(default_factory=asyncio.Lock)
    charge_on_solar_lower_limit: int = CHARGE_ON_SOLAR_LOWER_LIMIT_DEFAULT
    charge_on_solar_enabled: bool | None = None
    charge_on_solar_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    @property
    def polls_charge_limit(self) -> bool:
        """Whether this vehicle's charge limit comes from polling rather than the stream."""
        return self.poll or not firmware_at_least(self.firmware, "2024.26")


class TeslemetryChargeOnSolarStore:
    """Persist each vehicle's charge-on-solar settings for the config entry.

    The switch and lower limit number each send both values, and a registry-disabled
    entity's restore state expires, so the settings are stored independently of them.
    """

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize the store."""
        self._store = Store[dict[str, dict[str, Any]]](
            hass, STORAGE_VERSION, f"{DOMAIN}.charge_on_solar.{entry_id}"
        )
        self._data: dict[str, dict[str, Any]] = {}

    async def async_load(self, vehicles: list[TeslemetryVehicleData]) -> None:
        """Load the stored settings into each vehicle."""
        self._data = await self._store.async_load() or {}
        for vehicle in vehicles:
            if stored := self._data.get(vehicle.vin):
                vehicle.charge_on_solar_enabled = stored["enabled"]
                vehicle.charge_on_solar_lower_limit = stored["lower_limit"]

    @callback
    def async_save(self, vehicle: TeslemetryVehicleData) -> None:
        """Schedule saving a vehicle's current settings."""
        self._data[vehicle.vin] = {
            "enabled": vehicle.charge_on_solar_enabled,
            "lower_limit": vehicle.charge_on_solar_lower_limit,
        }
        self._store.async_delay_save(lambda: self._data)

    async def async_remove(self) -> None:
        """Remove the stored settings."""
        await self._store.async_remove()


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
