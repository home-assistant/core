"""API for the Minecraft Server integration."""


from dataclasses import dataclass
from enum import StrEnum

from mcstatus import BedrockServer, JavaServer
from mcstatus.status_response import BedrockStatusResponse, JavaStatusResponse


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


class MinecraftServerType(StrEnum):
    """Enumeration of Minecraft Server types."""

    JAVA_EDITION = "Java Edition"
    BEDROCK_EDITION = "Bedrock Edition"


class MinecraftServerAddressError(Exception):
    """Raised when the input address is invalid."""


class MinecraftServerConnectionError(Exception):
    """Raised when no data can be fechted from the server."""


class MinecraftServer:
    """Minecraft Server wrapper class for 3rd party library mcstatus."""

    _server: BedrockServer | JavaServer

    def __init__(self, server_type: MinecraftServerType, address: str) -> None:
        """Initialize server instance."""
        try:
            if server_type == MinecraftServerType.JAVA_EDITION:
                self._server = JavaServer.lookup(address)
            else:
                self._server = BedrockServer.lookup(address)
        except ValueError as error:
            raise MinecraftServerAddressError(
                f"{server_type} server address '{address}' is invalid (error: {error})"
            ) from error

    async def async_is_online(self) -> bool:
        """Check if the server is online, supporting both Java and Bedrock Edition servers."""
        try:
            await self.async_get_data()
        except MinecraftServerConnectionError:
            return False

        return True

    async def async_get_data(self) -> MinecraftServerData:
        """Get updated data from the server, supporting both Java and Bedrock Edition servers."""
        status_response: BedrockStatusResponse | JavaStatusResponse

        try:
            status_response = await self._server.async_status()
        except OSError as error:
            raise MinecraftServerConnectionError(
                f"Fetching data from the server failed (error: {error})"
            ) from error

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
