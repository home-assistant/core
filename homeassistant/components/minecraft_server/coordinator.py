"""The Minecraft Server integration."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

import aiodns
from mcstatus.server import JavaServer

from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import SCAN_INTERVAL, SRV_RECORD_PREFIX

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
        self._hass = hass

        # Server data
        self.unique_id = unique_id
        self.name = config_data[CONF_NAME]
        self.host = config_data[CONF_HOST]
        self.port = config_data[CONF_PORT]
        self.srv_record_checked = False

        # 3rd party library instance
        self._server = JavaServer(self.host, self.port)

    async def async_is_server_online(self) -> bool:
        """Check server connection using a 'status' request and return result."""
        server_online = False

        # Check once if host is a SRV record. If so, update server data.
        if not self.srv_record_checked:
            await self._async_check_srv_record()

        # Send a status request to the server.
        try:
            await self._server.async_status()
            server_online = True
        except OSError as error:
            _LOGGER.debug(
                (
                    "Error occurred while trying to check the connection to '%s:%s' -"
                    " OSError: %s"
                ),
                self.host,
                self.port,
                error,
            )

        return server_online

    async def _async_check_srv_record(self) -> None:
        """Check if the given host is a valid Minecraft SRV record."""
        self.srv_record_checked = True
        srv_record = None
        srv_query = None

        try:
            srv_query = await aiodns.DNSResolver().query(
                host=f"{SRV_RECORD_PREFIX}.{self.host}", qtype="SRV"
            )
        except aiodns.error.DNSError:
            # 'host' is not a SRV record.
            pass
        else:
            # 'host' is a valid SRV record, extract the data.
            srv_record = {
                CONF_HOST: srv_query[0].host,
                CONF_PORT: srv_query[0].port,
            }

            if srv_record is not None:
                _LOGGER.debug(
                    "'%s' is a valid Minecraft SRV record ('%s:%s')",
                    self.host,
                    srv_record[CONF_HOST],
                    srv_record[CONF_PORT],
                )
                # Overwrite host, port and 3rd party library instance
                # with data extracted out of SRV record.
                self.host = srv_record[CONF_HOST]
                self.port = srv_record[CONF_PORT]
                self._server = JavaServer(self.host, self.port)

    async def _async_update_data(self) -> MinecraftServerData:
        """Get server data from 3rd party library and update properties."""

        # Check once if host is a SRV record. If so, update server data.
        if not self.srv_record_checked:
            await self._async_check_srv_record()

        # Send status request to the server.
        try:
            status_response = await self._server.async_status()
        except OSError as error:
            raise UpdateFailed(error) from error

        # Got answer to request, update properties.
        players_list = []
        if status_response.players.sample is not None:
            for player in status_response.players.sample:
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
