"""Coordinate data for powerview devices."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from aiopvapi.shades import Shades

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import SHADE_DATA
from .shade_data import PowerviewShadeData

_LOGGER = logging.getLogger(__name__)


class PowerviewShadeUpdateCoordinator(DataUpdateCoordinator[PowerviewShadeData]):
    """DataUpdateCoordinator to gather data from a powerview hub."""

    def __init__(
        self,
        hass: HomeAssistant,
        shades: Shades,
        hub_address: str,
    ) -> None:
        """Initialize DataUpdateCoordinator to gather data for specific Powerview Hub."""
        self.shades = shades
        super().__init__(
            hass,
            _LOGGER,
            name=f"powerview hub {hub_address}",
            update_interval=timedelta(seconds=60),
        )

    async def _async_update_data(self) -> PowerviewShadeData:
        """Fetch data from shade endpoint."""

        async with asyncio.timeout(10):
            shade_entries = await self.shades.get_resources()

        if isinstance(shade_entries, bool):
            # hub returns boolean on a 204/423 empty response (maintenance)
            # continual polling results in inevitable error
            raise UpdateFailed("Powerview Hub is undergoing maintenance")

        if not shade_entries:
            raise UpdateFailed("Failed to fetch new shade data")

        # only update if shade_entries is valid
        self.data.store_group_data(shade_entries[SHADE_DATA])

        return self.data
