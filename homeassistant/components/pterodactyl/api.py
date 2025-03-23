"""API module of the Pterodactyl integration."""

from dataclasses import dataclass
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


class PterodactylNotInitializedError(Exception):
    """Raised when APIs are used although server instance is not initialized yet."""


@dataclass
class PterodactylData:
    """Data for the Pterodactyl server."""

    name: str
    uuid: str
    identifier: str
    state: str
    memory_utilization: int
    cpu_utilization: float
    disk_utilization: int
    network_rx_utilization: int
    network_tx_utilization: int
    uptime: int


class PterodactylAPI:
    """Wrapper for Pterodactyl's API."""

    pterodactyl: PterodactylClient | None
    identifiers: list[str]
    data_list: list[PterodactylData]

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
        except Exception as error:
            _LOGGER.exception("Unexpected exception occurred during initialization")
            raise PterodactylConnectionError(error) from error
        else:
            servers = paginated_response.collect()
            for server in servers:
                self.identifiers.append(server["attributes"]["identifier"])

            _LOGGER.debug("Identifiers of Pterodactyl servers: %s", self.identifiers)

    def get_index_from_identifier(self, identifier: str) -> int | None:
        """Get the index of the data list from the identifier."""
        for index, data in enumerate(self.data_list):
            if data.identifier == identifier:
                return index

        return None

    async def async_get_data_list(self) -> list[PterodactylData]:
        """Update the data from all Pterodactyl servers."""
        self.data_list = []
        current_identifier: str

        if self.pterodactyl is None:
            raise PterodactylNotInitializedError(
                "Pterodactyl API is not initialized yet"
            )

        try:
            for identifier in self.identifiers:
                current_identifier = identifier
                server = await self.hass.async_add_executor_job(
                    self.pterodactyl.client.servers.get_server, identifier
                )
                utilization = await self.hass.async_add_executor_job(
                    self.pterodactyl.client.servers.get_server_utilization, identifier
                )

                data = PterodactylData(
                    name=server["name"],
                    uuid=server["uuid"],
                    identifier=current_identifier,
                    state=utilization["current_state"],
                    cpu_utilization=utilization["resources"]["cpu_absolute"],
                    memory_utilization=utilization["resources"]["memory_bytes"],
                    disk_utilization=utilization["resources"]["disk_bytes"],
                    network_rx_utilization=utilization["resources"]["network_rx_bytes"],
                    network_tx_utilization=utilization["resources"]["network_tx_bytes"],
                    uptime=utilization["resources"]["uptime"],
                )

                self.data_list.append(data)
                _LOGGER.debug("%s", data)
        except (
            PydactylError,
            BadRequestError,
            PterodactylApiError,
        ) as error:
            raise PterodactylConnectionError(error) from error
        except Exception as error:
            _LOGGER.exception("Unexpected exception occurred during data update")
            raise PterodactylConnectionError(error) from error
        else:
            return self.data_list
