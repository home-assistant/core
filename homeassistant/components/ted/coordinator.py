"""Coordinator for The Energy Detective (TED) integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

import async_timeout
import httpx
from tedpy import TED

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

SCAN_INTERVAL = timedelta(seconds=60)
TIMEOUT = 50  # 10 seconds less than the scan interval


_LOGGER = logging.getLogger(__name__)


class TedUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching TED data from the gateway."""

    def __init__(self, hass: HomeAssistant, *, name: str, ted_reader: TED) -> None:
        """Initialize global TED data updater."""
        self.ted_reader = ted_reader

        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API endpoint."""
        data: dict[str, Any] = {}
        async with async_timeout.timeout(TIMEOUT):
            try:
                await self.ted_reader.update()
            except httpx.HTTPError as err:
                raise UpdateFailed(f"Error communicating with API: {err}") from err

            data["type"] = self.ted_reader.system_type
            data["net"] = self.ted_reader.energy()
            data["production"] = self.ted_reader.production()
            data["consumption"] = self.ted_reader.consumption()
            data["spyders"] = {}
            for spyder in self.ted_reader.spyders:
                for ctgroup in spyder.ctgroups:
                    data["spyders"][f"{spyder.position}.{ctgroup.position}"] = {
                        "name": ctgroup.description,
                        "energy": ctgroup.energy(),
                    }
            data["mtus"] = {}
            for mtu in self.ted_reader.mtus:
                data["mtus"][mtu.position] = {
                    "name": mtu.description,
                    "type": mtu.type,
                    "power": mtu.power(),
                    "energy": mtu.energy(),
                }

            _LOGGER.debug("Retrieved data from API: %s", data)

            return data
