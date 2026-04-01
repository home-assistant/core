"""Coordinator for the Tesla Powerwall integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, TypedDict

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

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import UPDATE_INTERVAL

if TYPE_CHECKING:
    from . import PowerwallDataManager

_LOGGER = logging.getLogger(__name__)

type PowerwallConfigEntry = ConfigEntry[PowerwallRuntimeData]


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

    coordinator: PowerwallUpdateCoordinator | None
    api_instance: Powerwall
    base_info: PowerwallBaseInfo
    api_changed: bool


class PowerwallUpdateCoordinator(DataUpdateCoordinator[PowerwallData]):
    """Coordinator for powerwall data."""

    config_entry: PowerwallConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: PowerwallConfigEntry,
        manager: PowerwallDataManager,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="Powerwall site",
            update_method=manager.async_update_data,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
            always_update=False,
        )
