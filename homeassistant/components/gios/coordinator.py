"""The GIOS component."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from aiohttp.client_exceptions import ClientConnectorError
from gios import Gios
from gios.exceptions import GiosError
from gios.model import GiosSensors

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import API_TIMEOUT, DOMAIN, SCAN_INTERVAL

if TYPE_CHECKING:
    from aiohttp import ClientSession

    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class GiosDataUpdateCoordinator(DataUpdateCoordinator[GiosSensors]):
    """Define an object to hold GIOS data."""

    def __init__(
        self, hass: HomeAssistant, session: ClientSession, station_id: int
    ) -> None:
        """Class to manage fetching GIOS data API."""
        self.gios = Gios(station_id, session)

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)

    async def _async_update_data(self) -> GiosSensors:
        """Update data via library."""
        try:
            async with asyncio.timeout(API_TIMEOUT):
                return await self.gios.async_update()
        except (GiosError, ClientConnectorError) as error:
            raise UpdateFailed(error) from error
