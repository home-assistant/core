"""DataUpdateCoordinator for Wibeee energy monitors."""

import logging
from typing import Any, override
from xml.etree.ElementTree import ParseError as XMLParseError

import aiohttp
from pywibeee import WibeeeAPI, WibeeeDeviceInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type WibeeeData = dict[str, dict[str, Any]]
type WibeeeConfigEntry = ConfigEntry[WibeeeCoordinator]


class WibeeeCoordinator(DataUpdateCoordinator[WibeeeData]):
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
            device_info = await self.api.async_fetch_device_info(retries=3)
        except (TimeoutError, aiohttp.ClientError) as exc:
            raise UpdateFailed(
                f"Could not connect to Wibeee at {self.api.host}: {exc}"
            ) from exc

        if device_info is None:
            raise UpdateFailed(
                f"No device info received from Wibeee at {self.api.host}"
            )

        self.device_info = device_info

    @override
    async def _async_update_data(self) -> WibeeeData:
        """Fetch data from the Wibeee device."""
        try:
            data = await self.api.async_fetch_sensors_data(retries=2)
        except (TimeoutError, aiohttp.ClientError, XMLParseError) as exc:
            raise UpdateFailed(
                f"Error fetching data from {self.api.host}: {exc}"
            ) from exc

        if data is None:
            raise UpdateFailed(f"No data received from Wibeee at {self.api.host}")

        return data
