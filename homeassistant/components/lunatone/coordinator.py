"""Coordinator for handling data fetching and updates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

import aiohttp
from lunatone_rest_api_client import Device, Devices, Info
from lunatone_rest_api_client.models import DevicesData, InfoData

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_DEVICES_SCAN_INTERVAL = timedelta(seconds=30)


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
        self, hass: HomeAssistant, config_entry: LunatoneConfigEntry, info_api: Info
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}-info",
            always_update=False,
        )
        self.info_api = info_api

    async def _async_update_data(self) -> InfoData:
        """Update info data."""
        try:
            await self.info_api.async_update()
        except aiohttp.ClientConnectionError as ex:
            raise UpdateFailed(
                "Unable to retrieve info data from Lunatone REST API"
            ) from ex

        if self.info_api.data is None:
            raise UpdateFailed("Did not receive info data from Lunatone REST API")
        return self.info_api.data


class LunatoneDevicesDataUpdateCoordinator(DataUpdateCoordinator[DevicesData]):
    """Data update coordinator for Lunatone devices."""

    config_entry: LunatoneConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: LunatoneConfigEntry,
        devices_api: Devices,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}-devices",
            always_update=False,
            update_interval=DEFAULT_DEVICES_SCAN_INTERVAL,
        )
        self.devices_api = devices_api
        self.device_api_mapping: dict[int, Device] = {}

    async def _async_update_data(self) -> DevicesData:
        """Update devices data."""
        try:
            await self.devices_api.async_update()
        except aiohttp.ClientConnectionError as ex:
            raise UpdateFailed(
                "Unable to retrieve devices data from Lunatone REST API"
            ) from ex

        if self.devices_api.data is None:
            raise UpdateFailed("Did not receive devices data from Lunatone REST API")

        for device in self.devices_api.devices:
            self.device_api_mapping.update({device.id: device})
        return self.devices_api.data
