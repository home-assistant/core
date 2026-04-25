"""Coordinator for the Tesla Powerwall integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any, TypedDict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import UPDATE_INTERVAL

if TYPE_CHECKING:
    from . import PowerwallDataManager

_LOGGER = logging.getLogger(__name__)


@dataclass
class PowerwallBaseInfo:
    """Base information for the powerwall."""

    unique_id: str  # gateway_din (PW2) or IP (PW3)
    site_name: str | None  # From site_info or None
    version: str | None  # Firmware version or None
    device_type: str  # "Powerwall 2" or "Powerwall 3"
    url: str
    is_powerwall3: bool


@dataclass
class MeterData:
    """Data for a single meter."""

    instant_power: float
    energy_exported: float
    energy_imported: float
    instant_average_voltage: float
    instant_total_current: float
    frequency: float


@dataclass
class PowerwallData:
    """Point in time data for the powerwall."""

    charge: float  # Battery percentage
    grid_status: str  # "UP" or "DOWN"
    grid_services_active: bool
    site: MeterData
    battery: MeterData
    load: MeterData
    solar: MeterData | None  # None if no solar


class PowerwallRuntimeData(TypedDict):
    """Runtime data for the powerwall."""

    coordinator: PowerwallUpdateCoordinator | None
    api_instance: Any  # pypowerwall.Powerwall
    base_info: PowerwallBaseInfo


# Type alias for config entry with runtime data (after RuntimeData is defined)
PowerwallConfigEntry = ConfigEntry[PowerwallRuntimeData]


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
