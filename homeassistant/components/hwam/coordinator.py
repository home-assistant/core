"""The StoveData update coordination."""

from __future__ import annotations

import asyncio
from datetime import timedelta

from hwamsmartctrl.airbox import Airbox
from hwamsmartctrl.stovedata import StoveData

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, LOGGER


class StoveDataUpdateCoordinator(DataUpdateCoordinator[StoveData]):
    """Class to manage the polling of the Airbox API."""

    def __init__(
        self,
        hass: HomeAssistant,
        airbox: Airbox,
    ) -> None:
        """Initialize the Coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=15),
        )
        self.airbox = airbox

    async def _async_setup(self):
        await self.airbox.connect()

    async def _async_update_data(self):
        async with asyncio.timeout(5):
            return await self.airbox.get_stove_data()

    @property
    def api(self) -> Airbox:
        """The Airbox API."""
        return self.airbox
