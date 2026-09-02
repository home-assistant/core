"""DataUpdateCoordinator for Wibeee energy monitors."""

import asyncio
import logging
from typing import Any, cast, override

import aiohttp
from pywibeee import WibeeeAPI, WibeeeDeviceInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DEVICE_INFO_TIMEOUT, DOMAIN

_LOGGER = logging.getLogger(__name__)

type WibeeeConfigEntry = ConfigEntry[WibeeeCoordinator]


class WibeeeCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Coordinator that polls a Wibeee energy monitor for sensor data."""

    config_entry: WibeeeConfigEntry
    device_info: WibeeeDeviceInfo

    def __init__(self, hass: HomeAssistant, config_entry: WibeeeConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=config_entry.title,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.api = WibeeeAPI(
            async_get_clientsession(hass), config_entry.data[CONF_HOST]
        )

    @override
    async def _async_setup(self) -> None:
        """Fetch device info once before the first refresh."""
        try:
            async with asyncio.timeout(DEVICE_INFO_TIMEOUT):
                device_info = await self.api.async_fetch_device_info(retries=0)
        except (TimeoutError, aiohttp.ClientError) as exc:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"host": self.api.host, "error": str(exc)},
            ) from exc

        if device_info is None:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="no_device_info",
                translation_placeholders={"host": self.api.host},
            )

        # All wibeee entries have a MAC unique_id
        expected_mac = cast(str, self.config_entry.unique_id)
        if device_info.mac_addr_formatted != expected_mac:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="unexpected_device",
                translation_placeholders={
                    "host": self.api.host,
                    "expected": expected_mac,
                    "found": device_info.mac_addr_formatted,
                },
            )

        self.device_info = device_info

    @override
    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch data from the Wibeee device."""
        try:
            data = await self.api.async_fetch_sensors_data(retries=2)
        except (TimeoutError, aiohttp.ClientError) as exc:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="update_error",
                translation_placeholders={"host": self.api.host, "error": str(exc)},
            ) from exc

        if data is None:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="no_data",
                translation_placeholders={"host": self.api.host},
            )

        return data
