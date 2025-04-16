"""Data Updace Coordinator for Portainer."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING

from pyportainer import (
    Portainer,
    PortainerAuthenticationError,
    PortainerConnectionError,
)
from pyportainer.models.docker import DockerContainer
from pyportainer.models.portainer import Endpoint

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from . import PortainerConfigEntry


@dataclass
class PortainerCoordinatorData:
    """Data class for Portainer Coordinator."""

    id: int
    name: str
    endpoint: Endpoint
    containers: dict[DockerContainer, DockerContainer]


class PortainerCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """Data Update Coordinator for Portainer."""

    portainer: Portainer
    config_entry: PortainerConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: PortainerConfigEntry,
        portainer: Portainer,
    ) -> None:
        """Initialize the Portainer Data Update Coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.portainer = portainer
        self.config_entry = config_entry
        self.endpoints: dict[int, PortainerCoordinatorData] = {}

    async def _async_update_data(self):
        """Fetch data from Portainer API."""
        _LOGGER.debug(
            "Fetching data from Portainer API: %s", self.config_entry.data[CONF_HOST]
        )

        try:
            endpoints = await self.portainer.get_endpoints()
            _LOGGER.debug("Fetched endpoints: %s", endpoints)
        except PortainerAuthenticationError as err:
            _LOGGER.exception("Authentication error")
            raise ConfigEntryAuthFailed(
                f"Invalid Portainer authentication. Error: {err}"
            ) from err
        except PortainerConnectionError as err:
            raise UpdateFailed(f"Error during Portainer setup: {err}") from err

        if not endpoints:
            raise UpdateFailed("No endpoints found")

        mapped_endpoints: dict[int, PortainerCoordinatorData] = {}
        for endpoint in endpoints:
            assert endpoint.id
            try:
                containers = await self.portainer.get_containers(endpoint.id)
            except PortainerConnectionError as err:
                _LOGGER.exception("Connection error")
                raise UpdateFailed(f"Error during Portainer setup: {err}") from err
            except PortainerAuthenticationError as err:
                _LOGGER.exception("Authentication error")
                raise UpdateFailed(
                    f"Invalid Portainer authentication. Error: {err}"
                ) from err

            mapped_endpoints[endpoint.id] = PortainerCoordinatorData(
                id=endpoint.id,
                name=endpoint.name,
                endpoint=endpoint,
                containers={container.id: container for container in containers},
            )

        self.endpoints = mapped_endpoints
        return self.endpoints
