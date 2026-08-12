"""Data update coordinator for the Papouch integration."""

from datetime import timedelta
import logging
from typing import override

import aiohttp
from aiopapouch import PapouchDevice, PapouchTransport

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class PapouchDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Papouch data."""

    def __init__(
        self,
        hass: HomeAssistant,
        api_client: PapouchTransport,
        entry: ConfigEntry,
        device: PapouchDevice,
    ) -> None:
        """Initialize the coordinator."""
        interval = entry.options.get("refresh_rate", DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=entry,
            update_interval=timedelta(seconds=interval),
        )
        self.api_client = api_client
        self.device = device

    @override
    async def _async_update_data(self) -> dict:
        """Fetch data from the device."""
        try:
            fresh_data = await self.api_client.fetch_data()
            return await self.device.parse_fresh_data(fresh_data)
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from None
