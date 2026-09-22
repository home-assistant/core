"""API module of the Pterodactyl integration."""

from dataclasses import dataclass
from enum import StrEnum
import logging

from pydactyl import PterodactylClient
from pydactyl.exceptions import BadRequestError, PterodactylApiError
from requests.exceptions import ConnectionError, HTTPError

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class PterodactylAuthorizationError(Exception):
    """Raised when access to server is unauthorized."""


class PterodactylConnectionError(Exception):
    """Raised when no data can be fechted from the server."""


@dataclass
class PterodactylGameServer:
    """Pterodactyl game server."""

    identifier: str
    is_suspended: bool


@dataclass
class PterodactylGameServerData:
    """Data of a Pterodactyl game server."""

    name: str
    uuid: str
    identifier: str
    state: str
    cpu_utilization: float | None
    cpu_limit: int
    disk_usage: int | None
    disk_limit: int
    memory_usage: int | None
    memory_limit: int
    network_inbound: int | None
    network_outbound: int | None
    uptime: int


class PterodactylCommand(StrEnum):
    """Command enum for the Pterodactyl server."""

    START_SERVER = "start"
    STOP_SERVER = "stop"
    RESTART_SERVER = "restart"
    FORCE_STOP_SERVER = "kill"


class PterodactylAPI:
    """Wrapper for Pterodactyl's API."""

    pterodactyl: PterodactylClient | None
    game_servers: list[PterodactylGameServer]

    def __init__(self, hass: HomeAssistant, host: str, api_key: str) -> None:
        """Initialize the Pterodactyl API."""
        self.hass = hass
        self.host = host
        self.api_key = api_key
        self.pterodactyl = None
        self.game_servers = []

    def get_game_servers(self) -> list[str]:
        """Get all game servers."""
        paginated_response = self.pterodactyl.client.servers.list_servers()  # type: ignore[union-attr]

        return paginated_response.collect()

    async def async_init(self):
        """Initialize the Pterodactyl API."""
        self.pterodactyl = PterodactylClient(self.host, self.api_key)

        try:
            game_servers = await self.hass.async_add_executor_job(self.get_game_servers)
        except (
            BadRequestError,
            PterodactylApiError,
            ConnectionError,
            StopIteration,
        ) as error:
            raise PterodactylConnectionError(error) from error
        except HTTPError as error:
            if error.response.status_code == 401:
                raise PterodactylAuthorizationError(error) from error

            raise PterodactylConnectionError(error) from error
        else:
            for game_server in game_servers:
                self.game_servers.append(
                    PterodactylGameServer(
                        identifier=game_server["attributes"]["identifier"],
                        is_suspended=game_server["attributes"]["is_suspended"],
                    )
                )

            _LOGGER.debug("Pterodactyl game servers: %s", self.game_servers)

    def get_server_data(
        self, game_server: PterodactylGameServer
    ) -> tuple[dict, dict | None]:
        """Get all data from the Pterodactyl game server."""
        server = self.pterodactyl.client.servers.get_server(game_server.identifier)  # type: ignore[union-attr]

        game_server.is_suspended = server["is_suspended"]

        if not game_server.is_suspended:
            utilization = self.pterodactyl.client.servers.get_server_utilization(  # type: ignore[union-attr]
                game_server.identifier
            )
        else:
            utilization = None

        return server, utilization

    async def async_get_data(self) -> dict[str, PterodactylGameServerData]:
        """Update the data from all Pterodactyl game servers."""
        data = {}

        for game_server in self.game_servers:
            try:
                server, utilization = await self.hass.async_add_executor_job(
                    self.get_server_data, game_server
                )
            except (BadRequestError, PterodactylApiError, ConnectionError) as error:
                raise PterodactylConnectionError(error) from error
            except HTTPError as error:
                if error.response.status_code == 401:
                    raise PterodactylAuthorizationError(error) from error

                raise PterodactylConnectionError(error) from error
            else:
                name = server["name"]
                uuid = server["uuid"]
                identifier = game_server.identifier
                cpu_limit = server["limits"]["cpu"]
                memory_limit = server["limits"]["memory"]
                disk_limit = server["limits"]["disk"]

                if utilization is None:
                    state = "suspended"
                    cpu_utilization = None
                    memory_usage = None
                    disk_usage = None
                    network_inbound = None
                    network_outbound = None
                    uptime = 0
                else:
                    state = utilization["current_state"]
                    cpu_utilization = utilization["resources"]["cpu_absolute"]
                    memory_usage = utilization["resources"]["memory_bytes"]
                    disk_usage = utilization["resources"]["disk_bytes"]
                    network_inbound = utilization["resources"]["network_rx_bytes"]
                    network_outbound = utilization["resources"]["network_tx_bytes"]
                    uptime = utilization["resources"]["uptime"]

                data[game_server.identifier] = PterodactylGameServerData(
                    name=name,
                    uuid=uuid,
                    identifier=identifier,
                    state=state,
                    cpu_utilization=cpu_utilization,
                    cpu_limit=cpu_limit,
                    disk_usage=disk_usage,
                    disk_limit=disk_limit,
                    memory_usage=memory_usage,
                    memory_limit=memory_limit,
                    network_inbound=network_inbound,
                    network_outbound=network_outbound,
                    uptime=uptime,
                )
                _LOGGER.debug("%s", data[game_server.identifier])

        return data

    async def async_send_command(
        self, identifier: str, command: PterodactylCommand
    ) -> None:
        """Send a command to the Pterodactyl game server."""
        try:
            await self.hass.async_add_executor_job(
                self.pterodactyl.client.servers.send_power_action,  # type: ignore[union-attr]
                identifier,
                command,
            )
        except (BadRequestError, PterodactylApiError, ConnectionError) as error:
            raise PterodactylConnectionError(error) from error
        except HTTPError as error:
            if error.response.status_code == 401:
                raise PterodactylAuthorizationError(error) from error

            raise PterodactylConnectionError(error) from error
