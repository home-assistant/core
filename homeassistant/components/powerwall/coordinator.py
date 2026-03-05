"""Coordinator for the Tesla Powerwall integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, TypedDict

from tesla_powerwall import Powerwall

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import UPDATE_INTERVAL
from .models import PowerwallBaseInfo, PowerwallData

if TYPE_CHECKING:
    from . import PowerwallDataManager

_LOGGER = logging.getLogger(__name__)

type PowerwallConfigEntry = ConfigEntry[PowerwallRuntimeData]


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
