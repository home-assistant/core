"""DataUpdateCoordinator for the Supla integration."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from asyncpysupla import SuplaAPI

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)


class SuplaCoordinator(DataUpdateCoordinator[dict[int, dict]]):
    """Class to manage fetching Supla channel data."""

    def __init__(
        self,
        hass: HomeAssistant,
        server: SuplaAPI,
        server_name: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"supla-{server_name}",
            update_interval=SCAN_INTERVAL,
        )
        self._server = server

    async def _async_update_data(self) -> dict[int, dict]:
        """Fetch channels from the Supla API."""
        async with asyncio.timeout(SCAN_INTERVAL.total_seconds()):
            return {
                channel["id"]: channel
                for channel in await self._server.get_channels(
                    include=["iodevice", "state", "connected"]
                )
            }
