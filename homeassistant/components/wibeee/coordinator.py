"""DataUpdateCoordinator for Wibeee energy monitors."""

from __future__ import annotations

import logging
from typing import Any
from xml.etree.ElementTree import ParseError as XMLParseError

import aiohttp
from pywibeee import WibeeeAPI

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

type WibeeeData = dict[str, dict[str, Any]] | None


class WibeeeCoordinator(DataUpdateCoordinator[WibeeeData]):
    """Coordinator that polls a Wibeee energy monitor for sensor data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        api: WibeeeAPI,
        *,
        config_entry: ConfigEntry,
        name: str,
    ) -> None:
        """Initialize the coordinator."""
        self.api = api
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=name,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )

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
