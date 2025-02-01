"""DataUpdateCoordinator for London underground integration."""

from __future__ import annotations

import asyncio
import logging
from typing import cast

from london_tube_status import TubeData

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class LondonTubeCoordinator(DataUpdateCoordinator[dict[str, dict[str, str]]]):
    """London Underground sensor coordinator."""

    def __init__(self, hass: HomeAssistant, data: TubeData) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=None,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self._data = data

    async def _async_update_data(self) -> dict[str, dict[str, str]]:
        async with asyncio.timeout(10):
            await self._data.update()
            return cast(dict[str, dict[str, str]], self._data.data)
