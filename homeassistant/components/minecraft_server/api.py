"""API for the Minecraft Server integration."""

from dataclasses import dataclass
from enum import StrEnum
import logging

from dns.resolver import LifetimeTimeout
from mcstatus import BedrockServer, JavaServer
from mcstatus.responses import BedrockStatusResponse, JavaStatusResponse

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

LOOKUP_TIMEOUT: float = 10
DATA_UPDATE_TIMEOUT: float = 10
DATA_UPDATE_RETRIES: int = 3


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
    players_list: list[str] | None = None

    # Data available only in 'Bedrock Edition'
    edition: str | None = None
    game_mode: str | None = None
    map_name: str | None = None


class MinecraftServerType(StrEnum):
    """Enumeration of Minecraft Server types."""

    BEDROCK_EDITION = "Bedrock Edition"
    JAVA_EDITION = "Java Edition"


class MinecraftServerAddressError(Exception):
    """Raised when the input address is invalid."""


class MinecraftServerConnectionError(Exception):
    """Raised when no data can be fechted from the server."""


class MinecraftServerNotInitializedError(Exception):
    """Raised when APIs are used although server instance is not initialized yet."""


class MinecraftServer:
    """Minecraft Server wrapper class for 3rd party library mcstatus."""

    _server: BedrockServer | JavaServer | None

    def __init__(
        self, hass: HomeAssistant, server_type: MinecraftServerType, address: str
    ) -> None:
        """Initialize server instance."""
        self._server = None
        self._hass = hass
        self._server_type = server_type
        self._address = address

    async def async_initialize(self) -> None:
        """Perform async initialization of server instance."""
        try:
            if self._server_type == MinecraftServerType.JAVA_EDITION:
                self._server = await JavaServer.async_lookup(self._address)
            else:
                self._server = await self._hass.async_add_executor_job(
                    BedrockServer.lookup, self._address
                )
        except (ValueError, LifetimeTimeout) as error:
            raise MinecraftServerAddressError(
                f"Lookup of '{self._address}' failed: {self._get_error_message(error)}"
            ) from error

        self._server.timeout = DATA_UPDATE_TIMEOUT

        _LOGGER.debug(
            "Initialized %s server instance with address '%s'",
            self._server_type,
            self._address,
        )

    async def async_is_online(self) -> bool:
        """Check if the server is online, supporting both Java and Bedrock Edition servers."""
        try:
            await self.async_get_data()
        except (
            MinecraftServerConnectionError,
            MinecraftServerNotInitializedError,
        ) as error:
            _LOGGER.debug(
                "Connection check of %s server failed: %s",
                self._server_type,
                self._get_error_message(error),
            )
            return False

        return True

    async def async_get_data(self) -> MinecraftServerData:
        """Get updated data from the server, supporting both Java and Bedrock Edition servers."""
        status_response: BedrockStatusResponse | JavaStatusResponse

        if self._server is None:
            raise MinecraftServerNotInitializedError(
                f"Server instance with address '{self._address}' is not initialized"
            )

        try:
            status_response = await self._server.async_status(tries=DATA_UPDATE_RETRIES)
        except OSError as error:
            raise MinecraftServerConnectionError(
                f"Status request to '{self._address}' failed: {self._get_error_message(error)}"
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
        players_list: list[str] = []

        if players := status_response.players.sample:
            players_list.extend(player.name for player in players)
            players_list.sort()

        return MinecraftServerData(
            latency=status_response.latency,
            motd=status_response.motd.to_plain(),
            players_max=status_response.players.max,
            players_online=status_response.players.online,
            protocol_version=status_response.version.protocol,
            version=status_response.version.name,
            players_list=players_list,
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
            edition=status_response.version.brand,
            game_mode=status_response.gamemode,
            map_name=status_response.map_name,
        )

    def _get_error_message(self, error: BaseException) -> str:
        """Get error message of an exception."""
        if not str(error):
            # Fallback to error type in case of an empty error message.
            return repr(error)

        return str(error)
