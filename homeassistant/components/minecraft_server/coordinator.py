"""The Minecraft Server integration."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
import logging

from mcstatus.server import BedrockServer, JavaServer
from mcstatus.status_response import BedrockStatusResponse, JavaStatusResponse

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_NAME, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

SCAN_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)


class MinecraftServerType(StrEnum):
    """Enumeration of Minecraft Server types."""

    JAVA_EDITION = "Java Edition"
    BEDROCK_EDITION = "Bedrock Edition"


@dataclass
class MinecraftServerData:
    """Representation of Minecraft Server data."""

    # Common data
    latency: float
    motd: str
    players_max: int
    players_online: int
    protocol_version: int
    version: str

    # Data available only in 'Java Edition'
    players_list: list[str] | None

    # Data available only in 'Bedrock Edition'
    edition: str | None
    game_mode: str | None
    map_name: str | None


class MinecraftServerCoordinator(DataUpdateCoordinator[MinecraftServerData]):
    """Minecraft Server data update coordinator."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize coordinator instance."""
        config_data = config_entry.data
        self.unique_id = config_entry.entry_id
        self.server_type = config_data[CONF_TYPE]

        super().__init__(
            hass=hass,
            name=config_data[CONF_NAME],
            logger=_LOGGER,
            update_interval=SCAN_INTERVAL,
        )

        self._server: BedrockServer | JavaServer
        try:
            if self.server_type == MinecraftServerType.JAVA_EDITION:
                self._server = JavaServer.lookup(config_data[CONF_ADDRESS])
            else:
                self._server = BedrockServer.lookup(config_data[CONF_ADDRESS])
        except ValueError as error:
            raise HomeAssistantError(
                f"Address in configuration entry cannot be parsed (error: {error}), please remove this device and add it again"
            ) from error

    async def _async_update_data(self) -> MinecraftServerData:
        """Get server data from 3rd party library and update properties."""
        status_response: BedrockStatusResponse | JavaStatusResponse

        try:
            status_response = await self._server.async_status()
        except OSError as error:
            raise UpdateFailed(error) from error

        if isinstance(status_response, JavaStatusResponse):
            data = self._extract_java_data(status_response)
        else:
            data = self._extract_bedrock_data(status_response)

        return data

    def _extract_java_data(
        self, status_response: JavaStatusResponse
    ) -> MinecraftServerData:
        """Extract Java Edition server data out of status response."""
        players_list = []

        if players := status_response.players.sample:
            for player in players:
                players_list.append(player.name)
            players_list.sort()

        return MinecraftServerData(
            latency=status_response.latency,
            motd=status_response.motd.to_plain(),
            players_max=status_response.players.max,
            players_online=status_response.players.online,
            protocol_version=status_response.version.protocol,
            version=status_response.version.name,
            players_list=players_list,
            edition=None,
            game_mode=None,
            map_name=None,
        )

    def _extract_bedrock_data(
        self, status_response: BedrockStatusResponse
    ) -> MinecraftServerData:
        """Extract Bedrock Edition server data out of status response."""
        return MinecraftServerData(
            latency=status_response.latency,
            motd=status_response.motd.to_plain(),
            players_max=status_response.players.max,
            players_online=status_response.players.online,
            protocol_version=status_response.version.protocol,
            version=status_response.version.name,
            players_list=None,
            edition=status_response.version.brand,
            game_mode=status_response.gamemode,
            map_name=status_response.map_name,
        )
