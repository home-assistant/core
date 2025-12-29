"""Data Update Coordinator for Portainer."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from pyportainer import (
    Portainer,
    PortainerAuthenticationError,
    PortainerConnectionError,
    PortainerTimeoutError,
)
from pyportainer.models.docker import (
    DockerContainer,
    DockerContainerStats,
    ImageInformation,
    LocalImageInformation,
)
from pyportainer.models.docker_inspect import DockerInfo, DockerInspect, DockerVersion
from pyportainer.models.portainer import Endpoint

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL, EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, ENDPOINT_STATUS_DOWN

type PortainerConfigEntry = ConfigEntry[PortainerCoordinator]

_LOGGER = logging.getLogger(__name__)

DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)
BEACON_SCAN_INTERVAL = timedelta(hours=1)


@dataclass
class PortainerCoordinatorData:
    """Data class for Portainer Coordinator."""

    id: int
    name: str | None
    endpoint: Endpoint
    containers: dict[str, PortainerContainerData]
    docker_version: DockerVersion
    docker_info: DockerInfo


@dataclass(slots=True)
class PortainerContainerData:
    """Container data held by the Portainer coordinator."""

    container: DockerContainer
    stats: DockerContainerStats
    stats_pre: DockerContainerStats | None


@dataclass(slots=True, kw_only=True)
class ContainerBeaconData:
    """Data class for Container Beacon Data."""

    core: DockerContainer
    container_inspect: DockerInspect
    image_info: ImageInformation
    local_image: LocalImageInformation
    new_digest: str | None
    image_update: bool = False


@dataclass
class PortainerBeaconData:
    """Data class for Portainer Beacon Data."""

    id: int
    name: str | None
    endpoint: Endpoint
    containers: dict[str, ContainerBeaconData]


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
                containers = await self.portainer.get_containers(endpoint.id)
                docker_version = await self.portainer.docker_version(endpoint.id)
                docker_info = await self.portainer.docker_info(endpoint.id)

                container_map: dict[str, PortainerContainerData] = {}

                container_stats_task = [
                    (
                        container,
                        self.portainer.container_stats(
                            endpoint_id=endpoint.id,
                            container_id=container.id,
                        ),
                    )
                    for container in containers
                ]

                container_stats_gather = await asyncio.gather(
                    *[task for _, task in container_stats_task],
                )
                for (container, _), container_stats in zip(
                    container_stats_task, container_stats_gather, strict=False
                ):
                    container_name = container.names[0].replace("/", " ").strip()

                    # Store previous stats if available. This is used to calculate deltas for CPU and network usage
                    # In the first call it will be None, since it has nothing to compare with
                    # Added a walrus pattern to check if not None on prev_container, to keep mypy happy. :)
                    container_map[container_name] = PortainerContainerData(
                        container=container,
                        stats=container_stats,
                        stats_pre=(
                            prev_container.stats
                            if self.data
                            and (prev_data := self.data.get(endpoint.id)) is not None
                            and (
                                prev_container := prev_data.containers.get(
                                    container_name
                                )
                            )
                            is not None
                            else None
                        ),
                    )
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
            (endpoint.id, container.container.id)
            for endpoint in mapped_endpoints.values()
            for container in endpoint.containers.values()
        }
        new_containers = current_containers - self.known_containers
        if new_containers:
            _LOGGER.debug("New containers found: %s", new_containers)
            self.known_containers.update(new_containers)


class PortainerBeaconCoordinator(DataUpdateCoordinator[dict[int, PortainerBeaconData]]):
    """Data Update Coordinator for Portainer periodic background tasks. It inherits from the main coordinator."""

    config_entry: PortainerConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: PortainerConfigEntry,
        portainer: Portainer,
        base: PortainerCoordinator,
    ) -> None:
        """Initialize the Portainer Beacon Data Update Coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}_beacon",
            update_interval=BEACON_SCAN_INTERVAL,
        )
        self.portainer = portainer
        self.base = base
        self._allow_registry_io: bool = False

        if not self._allow_registry_io:
            _LOGGER.debug(
                "Portainer Beacon Coordinator registry I/O is not running at startup"
            )
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, self._ha_started)

    async def _ha_started(self, event: Any) -> None:
        """Enable registry I/O after Home Assistant has started."""
        self._allow_registry_io = True
        _LOGGER.debug(
            "Portainer Beacon Coordinator registry I/O is now enabled after Home Assistant started"
        )
        await self.async_request_refresh()

    async def _async_update_data(self) -> dict[int, PortainerBeaconData]:
        """Perform periodic background tasks."""
        _LOGGER.debug("Performing Portainer Beacon Coordinator background tasks")

        mapped_endpoints: dict[int, PortainerBeaconData] = {}
        for endpoint_data in self.base.data.values():
            if endpoint_data.endpoint.status == ENDPOINT_STATUS_DOWN:
                _LOGGER.debug(
                    "Skipping offline endpoint: %s (ID: %d)",
                    endpoint_data.endpoint.name,
                    endpoint_data.endpoint.id,
                )
                continue

            try:
                containers = await self.portainer.get_containers(
                    endpoint_id=endpoint_data.endpoint.id
                )

                container_data: dict[str, ContainerBeaconData] = {}
                for container in containers:
                    # @ERWIN: Silly local stub data
                    # image_info = ImageInformation(
                    #     descriptor=ImageManifestDescriptor(
                    #         digest=f"sha256:stub-{container.id[:8]}"
                    #     )
                    # )
                    container_inspect = await self.portainer.inspect_container(
                        endpoint_id=endpoint_data.endpoint.id, container_id=container.id
                    )
                    local_image = await self.portainer.get_image(
                        endpoint_id=endpoint_data.endpoint.id,
                        image_id=str(container_inspect.image),
                    )

                    image_info = ImageInformation(descriptor=None)
                    if self._allow_registry_io:
                        update_available = False
                        image_info = await self.portainer.get_image_information(
                            endpoint_id=endpoint_data.endpoint.id,
                            image_id=str(container.image),
                        )

                    image_sha = (
                        local_image.repo_digests[0].split("@")[1]
                        if local_image.repo_digests
                        and isinstance(local_image.repo_digests[0], str)
                        else None
                    )

                    image_info_digest = (
                        image_info.descriptor.digest if image_info.descriptor else None
                    )
                    if update_available := image_info_digest != image_sha:
                        #  Works perfect for debugging. Can be refactored later on.
                        _LOGGER.debug(
                            "Container %s (ID: %s) on Endpoint %s (ID: %d) has an update available",
                            container.names[0],
                            container.id,
                            endpoint_data.endpoint.name,
                            endpoint_data.endpoint.id,
                        )

                    container_data[container.names[0].replace("/", " ").strip()] = (
                        ContainerBeaconData(
                            core=container,
                            container_inspect=container_inspect,
                            image_info=image_info,
                            local_image=local_image,
                            new_digest=image_info_digest,
                            image_update=update_available,
                        )
                    )
            except PortainerConnectionError as err:
                _LOGGER.exception("Connection error")
                raise UpdateFailed(
                    translation_domain=DOMAIN,
                    translation_key="cannot_connect",
                    translation_placeholders={"error": repr(err)},
                ) from err
            except PortainerAuthenticationError as err:
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="invalid_auth",
                    translation_placeholders={"error": repr(err)},
                ) from err
            _LOGGER.debug("Completed Portainer Beacon Coordinator background tasks")

            mapped_endpoints[endpoint_data.endpoint.id] = PortainerBeaconData(
                id=endpoint_data.endpoint.id,
                name=endpoint_data.endpoint.name,
                endpoint=endpoint_data.endpoint,
                containers=container_data,
            )

        return mapped_endpoints
