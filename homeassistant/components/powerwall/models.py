"""The powerwall integration models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

from tesla_powerwall import (
    BatteryResponse,
    DeviceType,
    GridStatus,
    MetersAggregatesResponse,
    Powerwall,
    PowerwallStatusResponse,
    SiteInfoResponse,
    SiteMasterResponse,
)

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


@dataclass
class PowerwallBaseInfo:
    """Base information for the powerwall integration."""

    gateway_din: str
    site_info: SiteInfoResponse
    status: PowerwallStatusResponse
    device_type: DeviceType
    serial_numbers: list[str]
    url: str
    batteries: dict[str, BatteryResponse]


@dataclass
class PowerwallData:
    """Point in time data for the powerwall integration."""

    charge: float
    site_master: SiteMasterResponse
    meters: MetersAggregatesResponse
    grid_services_active: bool
    grid_status: GridStatus
    backup_reserve: float | None
    batteries: dict[str, BatteryResponse]


class PowerwallRuntimeData(TypedDict):
    """Run time data for the powerwall."""

    coordinator: DataUpdateCoordinator[PowerwallData] | None
    api_instance: Powerwall
    base_info: PowerwallBaseInfo
    api_changed: bool
