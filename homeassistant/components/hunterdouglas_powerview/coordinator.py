"""Coordinate data for powerview devices."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from aiopvapi.helpers.aiorequest import PvApiMaintenance
from aiopvapi.hub import Hub
from aiopvapi.shades import Shades

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import HUB_EXCEPTIONS
from .shade_data import PowerviewShadeData

_LOGGER = logging.getLogger(__name__)


class PowerviewShadeUpdateCoordinator(DataUpdateCoordinator[PowerviewShadeData]):
    """DataUpdateCoordinator to gather data from a powerview hub."""

    def __init__(self, hass: HomeAssistant, shades: Shades, hub: Hub) -> None:
        """Initialize DataUpdateCoordinator to gather data for specific Powerview Hub."""
        self.shades = shades
        self.hub = hub
        # The hub tends to crash if there are multiple radio operations at the same time
        # but it seems to handle all other requests that do not use RF without issue
        # so we have a lock to prevent multiple radio operations at the same time
        self.radio_operation_lock = asyncio.Lock()
        super().__init__(
            hass,
            _LOGGER,
            name=f"powerview hub {hub.hub_address}",
            update_interval=timedelta(seconds=60),
        )

    async def _async_update_data(self) -> PowerviewShadeData:
        """Fetch data from shade endpoint."""

        try:
            shade_entries = await self.shades.get_shades()
        except PvApiMaintenance as error:
            # hub is undergoing maintenance, pause polling
            raise UpdateFailed(error) from error
        except HUB_EXCEPTIONS as error:
            raise UpdateFailed(
                f"Powerview Hub {self.hub.hub_address} did not return any data: {error}"
            ) from error

        if not shade_entries:
            raise UpdateFailed("No new shade data was returned")

        # only update if shade_entries is valid
        self.data.store_group_data(shade_entries)

        return self.data
