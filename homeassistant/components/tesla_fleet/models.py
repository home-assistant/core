"""The Tesla Fleet integration models."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from tesla_fleet_api.const import Scope, TeslaEnergyPeriod
from tesla_fleet_api.tesla import EnergySite, VehicleFleet

from homeassistant.helpers.device_registry import DeviceInfo

from .coordinator import (
    TeslaFleetEnergySiteHistoryCoordinator,
    TeslaFleetEnergySiteInfoCoordinator,
    TeslaFleetEnergySiteLiveCoordinator,
    TeslaFleetVehicleDataCoordinator,
)


class TeslaFleetEnergySiteReadOnly:
    """Expose only Energy Site operations needed for read-only telemetry."""

    __slots__ = (
        "__energy_history",
        "__live_status",
        "__site_info",
        "energy_site_id",
    )

    def __init__(self, api: EnergySite) -> None:
        """Initialize a read-only facade around an Energy Site client."""
        self.energy_site_id = api.energy_site_id
        self.__energy_history: Callable[
            [
                TeslaEnergyPeriod | str | None,
                str | None,
                str | None,
                str | None,
            ],
            Awaitable[dict[str, Any]],
        ] = api.energy_history
        self.__live_status: Callable[[], Awaitable[dict[str, Any]]] = api.live_status
        self.__site_info: Callable[[], Awaitable[dict[str, Any]]] = api.site_info

    async def energy_history(
        self,
        period: TeslaEnergyPeriod | str | None,
        start_date: str | None = None,
        end_date: str | None = None,
        time_zone: str | None = None,
    ) -> dict[str, Any]:
        """Return Energy Site history."""
        return await self.__energy_history(period, start_date, end_date, time_zone)

    async def live_status(self) -> dict[str, Any]:
        """Return Energy Site live status."""
        return await self.__live_status()

    async def site_info(self) -> dict[str, Any]:
        """Return Energy Site information."""
        return await self.__site_info()


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
