"""DataUpdateCoordinator for the Squeezebox integration."""

from asyncio import timeout
from collections.abc import Callable
from datetime import timedelta
import logging
import re
from typing import Any

from pysqueezebox import Player, Server

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    PLAYER_UPDATE_INTERVAL,
    SENSOR_UPDATE_INTERVAL,
    SIGNAL_PLAYER_REDISCOVERED,
    STATUS_API_TIMEOUT,
    STATUS_SENSOR_LASTSCAN,
    STATUS_SENSOR_NEEDSRESTART,
    STATUS_SENSOR_RESCAN,
)

_LOGGER = logging.getLogger(__name__)


class LMSStatusDataUpdateCoordinator(DataUpdateCoordinator):
    """LMS Status custom coordinator."""

    def __init__(self, hass: HomeAssistant, lms: Server) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=lms.name,
            update_interval=timedelta(seconds=SENSOR_UPDATE_INTERVAL),
            always_update=False,
        )
        self.lms = lms
        self.newversion_regex = re.compile("<.*$")

    async def _async_update_data(self) -> dict:
        """Fetch data from LMS status call.

        Then we process only a subset to make then nice for HA
        """
        async with timeout(STATUS_API_TIMEOUT):
            data = await self.lms.async_status()

        if not data:
            raise UpdateFailed("No data from status poll")
        _LOGGER.debug("Raw serverstatus %s=%s", self.lms.name, data)

        return self._prepare_status_data(data)

    def _prepare_status_data(self, data: dict) -> dict:
        """Sensors that need the data changing for HA presentation."""

        # Binary sensors
        # rescan bool are we rescanning alter poll not present if false
        data[STATUS_SENSOR_RESCAN] = STATUS_SENSOR_RESCAN in data
        # needsrestart bool pending lms plugin updates not present if false
        data[STATUS_SENSOR_NEEDSRESTART] = STATUS_SENSOR_NEEDSRESTART in data

        # Sensors that need special handling
        # 'lastscan': '1718431678', epoc -> ISO 8601 not always present
        data[STATUS_SENSOR_LASTSCAN] = (
            dt_util.utc_from_timestamp(int(data[STATUS_SENSOR_LASTSCAN]))
            if STATUS_SENSOR_LASTSCAN in data
            else None
        )

        _LOGGER.debug("Processed serverstatus %s=%s", self.lms.name, data)
        return data


class SqueezeBoxPlayerUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for Squeezebox players."""

    def __init__(self, hass: HomeAssistant, player: Player, server_uuid: str) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=player.name,
            update_interval=timedelta(seconds=PLAYER_UPDATE_INTERVAL),
            always_update=True,
        )
        self.player = player
        self.available = True
        self._remove_dispatcher: Callable | None = None
        self.server_uuid = server_uuid

    async def _async_update_data(self) -> dict[str, Any]:
        """Update Player if available, or listen for rediscovery if not."""
        if self.available:
            # Only update players available at last update, unavailable players are rediscovered instead
            await self.player.async_update()

            if self.player.connected is False:
                _LOGGER.debug("Player %s is not available", self.name)
                self.available = False

                # start listening for restored players
                self._remove_dispatcher = async_dispatcher_connect(
                    self.hass, SIGNAL_PLAYER_REDISCOVERED, self.rediscovered
                )
        return {}

    @callback
    def rediscovered(self, unique_id: str, connected: bool) -> None:
        """Make a player available again."""
        if unique_id == self.player.player_id and connected:
            self.available = True
            _LOGGER.debug("Player %s is available again", self.name)
            if self._remove_dispatcher:
                self._remove_dispatcher()
