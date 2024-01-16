"""The WittIOT integration coordinator."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

from aiohttp import ClientSession
from aiohttp.client_exceptions import ClientConnectorError
from wittiot import API
from wittiot.errors import WittiotError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

SCAN_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)


class WittiotDataUpdateCoordinator(DataUpdateCoordinator):
    """Define an object to hold WittIOT data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        # entry: ConfigEntry,
        session: ClientSession,
        ip: str,
    ) -> None:
        """Initialize."""
        # self.entry = entry
        self.ip = ip
        self.api = API(ip, session=session)
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(seconds=10)
        )

    async def _async_update_data(self) -> dict[str, str | float | int]:
        """Update data."""
        res = {}
        async with asyncio.timeout(10):
            try:
                res = await self.api.request_loc_allinfo()
            except (WittiotError, ClientConnectorError) as error:
                raise UpdateFailed(error) from error
        _LOGGER.debug("Get device data: %s", res)
        return res
