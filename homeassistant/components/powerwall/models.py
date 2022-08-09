"""The powerwall integration models."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

from requests import Session
from tesla_powerwall import (
    DeviceType,
    GridStatus,
    MetersAggregates,
    PowerwallStatus,
    SiteInfo,
    SiteMaster,
)

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


@dataclass
class PowerwallBaseInfo:
    """Base information for the powerwall integration."""

    gateway_din: None | str
    site_info: SiteInfo
    status: PowerwallStatus
    device_type: DeviceType
    serial_numbers: list[str]
    url: str


@dataclass
class PowerwallData:
    """Point in time data for the powerwall integration."""

    charge: float
    site_master: SiteMaster
    meters: MetersAggregates
    grid_services_active: bool
    grid_status: GridStatus
    backup_reserve: float | None


class PowerwallRuntimeData(TypedDict):
    """Run time data for the powerwall."""

    coordinator: DataUpdateCoordinator | None
    base_info: PowerwallBaseInfo
    api_changed: bool
    http_session: Session
