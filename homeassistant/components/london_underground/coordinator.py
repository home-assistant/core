"""DataUpdateCoordinator for London underground integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from london_tube_status import TubeData

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class LondonTubeCoordinator(DataUpdateCoordinator[Any]):
    """London Underground sensor coordinator."""

    def __init__(self, hass: HomeAssistant, data: TubeData) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self._data = data

    async def _async_update_data(self) -> Any:
        async with asyncio.timeout(10):
            await self._data.update()
            return self._data.data
