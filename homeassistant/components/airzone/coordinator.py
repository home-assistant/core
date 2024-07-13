"""The Airzone integration."""

from __future__ import annotations

from asyncio import timeout
from datetime import timedelta
import logging
from typing import Any

from aioairzone.const import AZD_NEW_SYSTEMS, AZD_NEW_ZONES
from aioairzone.exceptions import AirzoneError
from aioairzone.localapi import AirzoneLocalApi

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import AIOAIRZONE_DEVICE_TIMEOUT_SEC, DOMAIN

SCAN_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)


class AirzoneUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Class to manage fetching data from the Airzone device."""

    def __init__(self, hass: HomeAssistant, airzone: AirzoneLocalApi) -> None:
        """Initialize."""
        self.airzone = airzone

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )

    async def _async_check_new_devices(self, data: dict[str, Any]) -> None:
        """Reload entry if there are new devices."""
        if (
            len(data.get(AZD_NEW_SYSTEMS, [])) > 0
            or len(data.get(AZD_NEW_ZONES, [])) > 0
        ):
            assert self.config_entry
            self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        async with timeout(AIOAIRZONE_DEVICE_TIMEOUT_SEC):
            try:
                await self.airzone.update()
            except AirzoneError as error:
                raise UpdateFailed(error) from error
            data = self.airzone.data()
        await self._async_check_new_devices(data)
        return data
