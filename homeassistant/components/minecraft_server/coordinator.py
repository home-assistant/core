"""The Minecraft Server integration."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from mcstatus.server import JavaServer

from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from . import helpers
from .const import SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


@dataclass
class MinecraftServerData:
    """Representation of Minecraft Server data."""

    latency: float
    motd: str
    players_max: int
    players_online: int
    players_list: list[str]
    protocol_version: int
    version: str


class MinecraftServerCoordinator(DataUpdateCoordinator[MinecraftServerData]):
    """Minecraft Server data update coordinator."""

    _srv_record_checked = False

    def __init__(
        self, hass: HomeAssistant, unique_id: str, config_data: Mapping[str, Any]
    ) -> None:
        """Initialize coordinator instance."""
        super().__init__(
            hass=hass,
            name=config_data[CONF_NAME],
            logger=_LOGGER,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )

        # Server data
        self.unique_id = unique_id
        self._host = config_data[CONF_HOST]
        self._port = config_data[CONF_PORT]

        # 3rd party library instance
        self._server = JavaServer(self._host, self._port)

    async def _async_update_data(self) -> MinecraftServerData:
        """Get server data from 3rd party library and update properties."""

        # Check once if host is a valid Minecraft SRV record.
        if not self._srv_record_checked:
            self._srv_record_checked = True
            if srv_record := await helpers.async_check_srv_record(self._host):
                # Overwrite host, port and 3rd party library instance
                # with data extracted out of the SRV record.
                self._host = srv_record[CONF_HOST]
                self._port = srv_record[CONF_PORT]
                self._server = JavaServer(self._host, self._port)

        # Send status request to the server.
        try:
            status_response = await self._server.async_status()
        except OSError as error:
            raise UpdateFailed(error) from error

        # Got answer to request, update properties.
        players_list = []
        if players := status_response.players.sample:
            for player in players:
                players_list.append(player.name)
            players_list.sort()

        return MinecraftServerData(
            version=status_response.version.name,
            protocol_version=status_response.version.protocol,
            players_online=status_response.players.online,
            players_max=status_response.players.max,
            players_list=players_list,
            latency=status_response.latency,
            motd=status_response.motd.to_plain(),
        )
