"""API module of the Pterodactyl integration."""

from dataclasses import dataclass
from enum import StrEnum
import logging

from pydactyl import PterodactylClient
from pydactyl.exceptions import (
    BadRequestError,
    ClientConfigError,
    PterodactylApiError,
    PydactylError,
)

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class PterodactylConfigurationError(Exception):
    """Raised when the configuration is invalid."""


class PterodactylConnectionError(Exception):
    """Raised when no data can be fechted from the server."""


@dataclass
class PterodactylData:
    """Data for the Pterodactyl server."""

    name: str
    uuid: str
    identifier: str
    state: str
    cpu_utilization: float
    cpu_limit: int
    disk_usage: int
    disk_limit: int
    memory_usage: int
    memory_limit: int
    network_inbound: int
    network_outbound: int
    uptime: int


class PterodactylCommands(StrEnum):
    """Command enums for the Pterodactyl server."""

    START_SERVER = "start"
    STOP_SERVER = "stop"
    RESTART_SERVER = "restart"
    FORCE_STOP_SERVER = "kill"


class PterodactylAPI:
    """Wrapper for Pterodactyl's API."""

    pterodactyl: PterodactylClient | None
    identifiers: list[str]

    def __init__(self, hass: HomeAssistant, host: str, api_key: str) -> None:
        """Initialize the Pterodactyl API."""
        self.hass = hass
        self.host = host
        self.api_key = api_key
        self.pterodactyl = None
        self.identifiers = []

    async def async_init(self):
        """Initialize the Pterodactyl API."""
        self.pterodactyl = PterodactylClient(self.host, self.api_key)

        try:
            paginated_response = await self.hass.async_add_executor_job(
                self.pterodactyl.client.servers.list_servers
            )
        except ClientConfigError as error:
            raise PterodactylConfigurationError(error) from error
        except (
            PydactylError,
            BadRequestError,
            PterodactylApiError,
        ) as error:
            raise PterodactylConnectionError(error) from error
        else:
            game_servers = paginated_response.collect()
            for game_server in game_servers:
                self.identifiers.append(game_server["attributes"]["identifier"])

            _LOGGER.debug("Identifiers of Pterodactyl servers: %s", self.identifiers)

    def get_server_data(self, identifier: str) -> tuple[dict, dict]:
        """Get all data from the Pterodactyl server."""
        server = self.pterodactyl.client.servers.get_server(identifier)  # type: ignore[union-attr]
        utilization = self.pterodactyl.client.servers.get_server_utilization(  # type: ignore[union-attr]
            identifier
        )

        return server, utilization

    async def async_get_data(self) -> dict[str, PterodactylData]:
        """Update the data from all Pterodactyl servers."""
        data = {}

        for identifier in self.identifiers:
            try:
                server, utilization = await self.hass.async_add_executor_job(
                    self.get_server_data, identifier
                )
            except (
                PydactylError,
                BadRequestError,
                PterodactylApiError,
            ) as error:
                raise PterodactylConnectionError(error) from error
            else:
                data[identifier] = PterodactylData(
                    name=server["name"],
                    uuid=server["uuid"],
                    identifier=identifier,
                    state=utilization["current_state"],
                    cpu_utilization=utilization["resources"]["cpu_absolute"],
                    cpu_limit=server["limits"]["cpu"],
                    memory_usage=utilization["resources"]["memory_bytes"],
                    memory_limit=server["limits"]["memory"],
                    disk_usage=utilization["resources"]["disk_bytes"],
                    disk_limit=server["limits"]["disk"],
                    network_inbound=utilization["resources"]["network_rx_bytes"],
                    network_outbound=utilization["resources"]["network_tx_bytes"],
                    uptime=utilization["resources"]["uptime"],
                )

                _LOGGER.debug("%s", data[identifier])

        return data

    async def async_send_command(
        self, identifier: str, command: PterodactylCommands
    ) -> None:
        """Send a command to the Pterodactyl server."""
        try:
            await self.hass.async_add_executor_job(
                self.pterodactyl.client.servers.send_power_action,  # type: ignore[union-attr]
                identifier,
                command,
            )
        except (
            PydactylError,
            BadRequestError,
            PterodactylApiError,
        ) as error:
            raise PterodactylConnectionError(error) from error
