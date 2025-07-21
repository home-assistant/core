"""Coordinator for handling data fetching and updates."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from lunatone_rest_api_client import Devices, Info
from lunatone_rest_api_client.models import DevicesData, InfoData

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class LunatoneData:
    """Data for Lunatone integration."""

    coordinator_info: LunatoneInfoDataUpdateCoordinator
    coordinator_devices: LunatoneDevicesDataUpdateCoordinator


type LunatoneConfigEntry = ConfigEntry[LunatoneData]


class LunatoneInfoDataUpdateCoordinator(DataUpdateCoordinator[InfoData]):
    """Data update coordinator for Lunatone info."""

    config_entry: LunatoneConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: LunatoneConfigEntry,
        info: Info,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}-info",
            always_update=False,
        )
        self.info = info

    async def _async_update_data(self) -> InfoData:
        """Update info data."""
        await self.info.async_update()
        return self.info.data


class LunatoneDevicesDataUpdateCoordinator(DataUpdateCoordinator[DevicesData]):
    """Data update coordinator for Lunatone devices."""

    config_entry: LunatoneConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: LunatoneConfigEntry,
        devices: Devices,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}-devices",
            always_update=False,
        )
        self.devices = devices

    async def _async_update_data(self) -> DevicesData:
        """Update devices data."""
        await self.devices.async_update()
        return self.devices.data
