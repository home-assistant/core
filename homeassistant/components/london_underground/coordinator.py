"""DataUpdateCoordinator for London underground integration."""
from __future__ import annotations

import asyncio
import logging

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class LondonTubeCoordinator(DataUpdateCoordinator):
    """London Underground sensor coordinator."""

    def __init__(self, hass, data):
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self._data = data

    async def _async_update_data(self):
        async with asyncio.timeout(10):
            await self._data.update()
            return self._data.data
