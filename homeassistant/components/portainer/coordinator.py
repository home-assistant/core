"""Data Update Coordinator for Portainer."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
import logging

from pyportainer import (
    Portainer,
    PortainerAuthenticationError,
    PortainerConnectionError,
    PortainerTimeoutError,
)
from pyportainer.models.docker import (
    DockerContainer,
    DockerContainerStats,
    DockerSystemDF,
)
from pyportainer.models.docker_inspect import DockerInfo, DockerVersion
from pyportainer.models.portainer import Endpoint

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONTAINER_STATE_RUNNING, DOMAIN, ENDPOINT_STATUS_DOWN

type PortainerConfigEntry = ConfigEntry[PortainerCoordinator]

_LOGGER = logging.getLogger(__name__)

DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)


@dataclass
class PortainerCoordinatorData:
    """Data class for Portainer Coordinator."""

    id: int
    name: str | None
    endpoint: Endpoint
    containers: dict[str, PortainerContainerData]
    docker_version: DockerVersion
    docker_info: DockerInfo
    docker_system_df: DockerSystemDF


@dataclass(slots=True)
class PortainerContainerData:
    """Container data held by the Portainer coordinator."""

    container: DockerContainer
    stats: DockerContainerStats | None
    stats_pre: DockerContainerStats | None


class PortainerCoordinator(DataUpdateCoordinator[dict[int, PortainerCoordinatorData]]):
    """Data Update Coordinator for Portainer."""

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
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.portainer = portainer

        self.known_endpoints: set[int] = set()
        self.known_containers: set[tuple[int, str]] = set()

        self.new_endpoints_callbacks: list[
            Callable[[list[PortainerCoordinatorData]], None]
        ] = []
        self.new_containers_callbacks: list[
            Callable[
                [list[tuple[PortainerCoordinatorData, PortainerContainerData]]], None
            ]
        ] = []

    async def _async_setup(self) -> None:
        """Set up the Portainer Data Update Coordinator."""
        try:
            await self.portainer.get_endpoints()
        except PortainerAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
                translation_placeholders={"error": repr(err)},
            ) from err
        except PortainerConnectionError as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": repr(err)},
            ) from err
        except PortainerTimeoutError as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="timeout_connect",
                translation_placeholders={"error": repr(err)},
            ) from err

    async def _async_update_data(self) -> dict[int, PortainerCoordinatorData]:
        """Fetch data from Portainer API."""
        _LOGGER.debug(
            "Fetching data from Portainer API: %s", self.config_entry.data[CONF_URL]
        )

        try:
            endpoints = await self.portainer.get_endpoints()
        except PortainerAuthenticationError as err:
            _LOGGER.error("Authentication error: %s", repr(err))
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
                translation_placeholders={"error": repr(err)},
            ) from err
        except PortainerConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"error": repr(err)},
            ) from err

        mapped_endpoints: dict[int, PortainerCoordinatorData] = {}
        for endpoint in endpoints:
            if endpoint.status == ENDPOINT_STATUS_DOWN:
                _LOGGER.debug(
                    "Skipping offline endpoint: %s (ID: %d)",
                    endpoint.name,
                    endpoint.id,
                )
                continue

            try:
                (
                    containers,
                    docker_version,
                    docker_info,
                    docker_system_df,
                ) = await asyncio.gather(
                    self.portainer.get_containers(endpoint.id),
                    self.portainer.docker_version(endpoint.id),
                    self.portainer.docker_info(endpoint.id),
                    self.portainer.docker_system_df(endpoint.id),
                )

                prev_endpoint = self.data.get(endpoint.id) if self.data else None
                container_map: dict[str, PortainerContainerData] = {}

                # Map containers, started and stopped
                for container in containers:
                    container_name = self._get_container_name(container.names[0])
                    prev_container = (
                        prev_endpoint.containers[container_name]
                        if prev_endpoint
                        else None
                    )
                    container_map[container_name] = PortainerContainerData(
                        container=container,
                        stats=None,
                        stats_pre=prev_container.stats if prev_container else None,
                    )

                # Separately fetch stats for running containers
                running_containers = [
                    container
                    for container in containers
                    if container.state == CONTAINER_STATE_RUNNING
                ]
                if running_containers:
                    container_stats = dict(
                        zip(
                            (
                                self._get_container_name(container.names[0])
                                for container in running_containers
                            ),
                            await asyncio.gather(
                                *(
                                    self.portainer.container_stats(
                                        endpoint_id=endpoint.id,
                                        container_id=container.id,
                                    )
                                    for container in running_containers
                                )
                            ),
                            strict=False,
                        )
                    )

                    # Now assign stats to the containers
                    for container_name, stats in container_stats.items():
                        container_map[container_name].stats = stats
            except PortainerConnectionError as err:
                _LOGGER.exception("Connection error")
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="cannot_connect",
                    translation_placeholders={"error": repr(err)},
                ) from err
            except PortainerAuthenticationError as err:
                _LOGGER.exception("Authentication error")
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="invalid_auth",
                    translation_placeholders={"error": repr(err)},
                ) from err

            mapped_endpoints[endpoint.id] = PortainerCoordinatorData(
                id=endpoint.id,
                name=endpoint.name,
                endpoint=endpoint,
                containers=container_map,
                docker_version=docker_version,
                docker_info=docker_info,
                docker_system_df=docker_system_df,
            )

        self._async_add_remove_endpoints(mapped_endpoints)

        return mapped_endpoints

    def _async_add_remove_endpoints(
        self, mapped_endpoints: dict[int, PortainerCoordinatorData]
    ) -> None:
        """Add new endpoints, remove non-existing endpoints."""
        current_endpoints = {endpoint.id for endpoint in mapped_endpoints.values()}
        new_endpoints = current_endpoints - self.known_endpoints
        if new_endpoints:
            _LOGGER.debug("New endpoints found: %s", new_endpoints)
            self.known_endpoints.update(new_endpoints)

        # Surprise, we also handle containers here :)
        current_containers = {
            (endpoint.id, container_name)
            for endpoint in mapped_endpoints.values()
            for container_name in endpoint.containers
        }
        new_containers = current_containers - self.known_containers
        if new_containers:
            _LOGGER.debug("New containers found: %s", new_containers)
            self.known_containers.update(new_containers)

    def _get_container_name(self, container_name: str) -> str:
        """Sanitize to get a proper container name."""
        return container_name.replace("/", " ").strip()
