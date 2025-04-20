"""Data Updace Coordinator for Portainer."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import TYPE_CHECKING

from pyportainer import (
    Portainer,
    PortainerAuthenticationError,
    PortainerConnectionError,
)
from pyportainer.models.docker import DockerContainer
from pyportainer.models.portainer import Endpoint

from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)

if TYPE_CHECKING:
    from . import PortainerConfigEntry


@dataclass
class PortainerCoordinatorData:
    """Data class for Portainer Coordinator."""

    id: int
    name: str | None
    endpoint: Endpoint
    containers: dict[str, DockerContainer] | None


class PortainerCoordinator(DataUpdateCoordinator[dict[int, PortainerCoordinatorData]]):
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

    async def _async_update_data(self) -> dict[int, PortainerCoordinatorData]:
        """Fetch data from Portainer API."""
        _LOGGER.debug(
            "Fetching data from Portainer API: %s", self.config_entry.data[CONF_URL]
        )

        try:
            endpoints = await self.portainer.get_endpoints()
            _LOGGER.debug("Fetched endpoints: %s", endpoints)
        except PortainerAuthenticationError as err:
            _LOGGER.exception("Authentication error")
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err
        except PortainerConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err

        mapped_endpoints: dict[int, PortainerCoordinatorData] = {}
        for endpoint in endpoints:
            if TYPE_CHECKING:
                assert endpoint.id
            try:
                containers = await self.portainer.get_containers(endpoint.id)
            except PortainerConnectionError as err:
                _LOGGER.exception("Connection error")
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="cannot_connect",
                ) from err
            except PortainerAuthenticationError as err:
                _LOGGER.exception("Authentication error")
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="invalid_auth",
                ) from err

            mapped_endpoints[endpoint.id] = PortainerCoordinatorData(
                id=endpoint.id,
                name=endpoint.name,
                endpoint=endpoint,
                containers={
                    str(container.id): container
                    for container in containers
                    if container.id is not None
                },  # This will be addressed in a later release of pyportainer to be explicit in a str and not str | None
            )

        self.endpoints = mapped_endpoints
        return mapped_endpoints
