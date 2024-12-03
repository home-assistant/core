"""The MusicCast integration."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from aiomusiccast import MusicCastConnectionException
from aiomusiccast.musiccast_device import MusicCastData, MusicCastDevice

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

if TYPE_CHECKING:
    from .entity import MusicCastDeviceEntity

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)


class MusicCastDataUpdateCoordinator(DataUpdateCoordinator[MusicCastData]):
    """Class to manage fetching data from the API."""

    def __init__(self, hass: HomeAssistant, client: MusicCastDevice) -> None:
        """Initialize."""
        self.musiccast = client

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.entities: list[MusicCastDeviceEntity] = []

    async def _async_update_data(self) -> MusicCastData:
        """Update data via library."""
        try:
            await self.musiccast.fetch()
        except MusicCastConnectionException as exception:
            raise UpdateFailed from exception
        return self.musiccast.data
