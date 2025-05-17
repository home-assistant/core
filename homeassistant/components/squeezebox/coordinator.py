"""DataUpdateCoordinator for the Squeezebox integration."""

from __future__ import annotations

from asyncio import timeout
from collections.abc import Callable
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Any

from pysqueezebox import Player, Server
from pysqueezebox.player import Alarm

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

if TYPE_CHECKING:
    from . import SqueezeboxConfigEntry

from .const import (
    DOMAIN,
    PLAYER_UPDATE_INTERVAL,
    SENSOR_UPDATE_INTERVAL,
    SIGNAL_ALARM_DISCOVERED,
    SIGNAL_PLAYER_REDISCOVERED,
    STATUS_API_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


class LMSStatusDataUpdateCoordinator(DataUpdateCoordinator):
    """LMS Status custom coordinator."""

    config_entry: SqueezeboxConfigEntry

    def __init__(
        self, hass: HomeAssistant, config_entry: SqueezeboxConfigEntry, lms: Server
    ) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=lms.name,
            update_interval=timedelta(seconds=SENSOR_UPDATE_INTERVAL),
            always_update=False,
        )
        self.lms = lms
        self.can_server_restart = False

    async def _async_setup(self) -> None:
        """Query LMS capabilities."""
        result = await self.lms.async_query("can", "restartserver", "?")
        if result and "_can" in result and result["_can"] == 1:
            _LOGGER.debug("Can restart %s", self.lms.name)
            self.can_server_restart = True
        else:
            _LOGGER.warning("Can't query server capabilities %s", self.lms.name)

    async def _async_update_data(self) -> dict:
        """Fetch data from LMS status call.

        Then we process only a subset to make then nice for HA
        """
        async with timeout(STATUS_API_TIMEOUT):
            data: dict | None = await self.lms.async_prepared_status()

        if not data:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="coordinator_no_data",
            )
        _LOGGER.debug("Raw serverstatus %s=%s", self.lms.name, data)

        return data


class SqueezeBoxPlayerUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for Squeezebox players."""

    config_entry: SqueezeboxConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: SqueezeboxConfigEntry,
        player: Player,
        server_uuid: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=player.name,
            update_interval=timedelta(seconds=PLAYER_UPDATE_INTERVAL),
            always_update=True,
        )
        self.player = player
        self.available = True
        self.known_alarms: list[str] = []
        self._remove_dispatcher: Callable | None = None
        self.player_uuid = format_mac(player.player_id)
        self.server_uuid = server_uuid
        self.data: dict[str, Any] = {}

    async def _async_update_data(self) -> dict[str, Any]:
        """Update the Player() object if available, or listen for rediscovery if not."""
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
            elif self.player.alarms:
                for alarm in self.player.alarms:
                    if alarm["id"] not in self.known_alarms:
                        self.known_alarms.append(alarm["id"])
                        async_dispatcher_send(
                            self.hass, SIGNAL_ALARM_DISCOVERED, alarm, self
                        )
                alarm_dict: dict[str, Alarm] = {
                    alarm["id"]: alarm for alarm in self.player.alarms
                }
                return {"alarms": alarm_dict}
        return {}

    @callback
    def rediscovered(self, unique_id: str, connected: bool) -> None:
        """Make a player available again."""
        if unique_id == self.player.player_id and connected:
            self.available = True
            _LOGGER.debug("Player %s is available again", self.name)
            if self._remove_dispatcher:
                self._remove_dispatcher()
