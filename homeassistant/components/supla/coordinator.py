"""Data update coordinator for SUPLA."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from asyncpysupla import SuplaAPI

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)


class SuplaCoordinator(DataUpdateCoordinator[dict[int, dict[str, Any]]]):
    """Coordinator for SUPLA server data."""

    config_entry: None

    def __init__(self, hass: HomeAssistant, server: SuplaAPI, server_name: str) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{server_name}",
            update_interval=SCAN_INTERVAL,
        )
        self.server = server

    async def _async_update_data(self) -> dict[int, dict[str, Any]]:
        """Fetch channels data from SUPLA server."""
        async with asyncio.timeout(SCAN_INTERVAL.total_seconds()):
            return {
                channel["id"]: channel
                for channel in await self.server.get_channels(
                    include=["iodevice", "state", "connected"]
                )
            }
