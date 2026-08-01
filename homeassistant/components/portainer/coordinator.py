"""Data Update Coordinator for Portainer."""

from abc import abstractmethod
import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
import logging
import time
from typing import override

from pyportainer import (
    DockerContainerState,
    EndpointStatus,
    Portainer,
    PortainerAuthenticationError,
    PortainerConnectionError,
    PortainerTimeoutError,
)
from pyportainer.models.docker import (
    DockerContainer,
    DockerContainerStats,
    DockerSystemDF,
    DockerVolume,
    DockerVolumeUsageData,
    LocalImageInformation,
    PortainerImageUpdateStatus,
)
from pyportainer.models.docker_inspect import DockerInfo, DockerInspect, DockerVersion
from pyportainer.models.portainer import Endpoint
from pyportainer.models.stacks import Stack
from pyportainer.watcher import PortainerImageWatcher

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .util import sanitize_container_name

type PortainerConfigEntry = ConfigEntry[PortainerCoordinator]

_LOGGER = logging.getLogger(__name__)

DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)
DEFAULT_DF_SCAN_INTERVAL = timedelta(minutes=30)


@dataclass
class PortainerCoordinatorData:
    """Data class for Portainer Coordinator."""

    id: int
    name: str | None
    endpoint: Endpoint
    containers: dict[str, PortainerContainerData]
    docker_version: DockerVersion
    docker_info: DockerInfo
    stacks: dict[str, PortainerStackData]
    volumes: dict[str, PortainerVolumeData]


@dataclass(slots=True)
class PortainerContainerData:
    """Container data held by the Portainer coordinator."""

    container: DockerContainer
    container_inspect: DockerInspect
    local_image: LocalImageInformation
    stack: Stack | None
    stats: DockerContainerStats | None
    stats_pre: DockerContainerStats | None
    image_status: PortainerImageUpdateStatus | None = None


@dataclass(slots=True)
class PortainerStackData:
    """Stack data held by the Portainer coordinator."""

    stack: Stack
    container_count: int = 0


@dataclass(slots=True)
class PortainerVolumeData:
    """Volume data held by the Portainer coordinator."""

    volume: DockerVolume


class PortainerBaseCoordinator[_DataT](DataUpdateCoordinator[_DataT]):
    """Base coordinator for Portainer."""

    config_entry: PortainerConfigEntry
    _update_interval: timedelta

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: PortainerConfigEntry,
        portainer: Portainer,
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=self._update_interval,
        )
        self.portainer = portainer

        self.known_endpoints: set[int] = set()
        self.known_containers: set[tuple[int, str]] = set()
        self.known_stacks: set[tuple[int, str]] = set()
        self.known_volumes: set[tuple[int, str]] = set()

        self.new_endpoints_callbacks: list[
            Callable[[list[PortainerCoordinatorData]], None]
        ] = []
        self.new_containers_callbacks: list[
            Callable[
                [list[tuple[PortainerCoordinatorData, PortainerContainerData]]], None
            ]
        ] = []
        self.new_stacks_callbacks: list[
            Callable[[list[tuple[PortainerCoordinatorData, PortainerStackData]]], None]
        ] = []
        self.new_volumes_callbacks: list[
            Callable[[list[tuple[PortainerCoordinatorData, PortainerVolumeData]]], None]
        ] = []

    @override
    async def _async_setup(self) -> None:
        """Set up the Portainer Data Update Coordinator."""
        try:
            await self.portainer.portainer_system_status()
        except PortainerAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err
        except PortainerConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err
        except PortainerTimeoutError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="timeout_connect",
            ) from err

    @abstractmethod
    async def update_data(self) -> _DataT:
        """Update coordinator data."""

    @override
    async def _async_update_data(self) -> _DataT:
        """Fetch per coordinator specific data."""
        try:
            return await self.update_data()
        except PortainerAuthenticationError as err:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
            ) from err
        except PortainerConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err
        except PortainerTimeoutError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="timeout_connect",
            ) from err


class PortainerCoordinator(
    PortainerBaseCoordinator[dict[int, PortainerCoordinatorData]]
):
    """Data Update Coordinator for Portainer."""

    config_entry: PortainerConfigEntry
    docker_disk_space: PortainerDockerDiskSpaceCoordinator | None = None
    watcher: PortainerImageWatcher | None = None
    _update_interval = DEFAULT_SCAN_INTERVAL

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: PortainerConfigEntry,
        portainer: Portainer,
    ) -> None:
        """Initialize."""
        super().__init__(hass, config_entry, portainer)
        self._image_cache: dict[
            tuple[int, str], tuple[float, LocalImageInformation]
        ] = {}

    @override
    async def update_data(self) -> dict[int, PortainerCoordinatorData]:
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
            ) from err
        except PortainerConnectionError as err:
            raise UpdateFailed(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err

        mapped_endpoints: dict[int, PortainerCoordinatorData] = {}
        for endpoint in endpoints:
            if endpoint.status == EndpointStatus.DOWN:
                _LOGGER.debug(
                    "Skipping offline endpoint: %s (ID: %d)",
                    endpoint.name,
                    endpoint.id,
                )
                continue

            (
                containers,
                docker_version,
                docker_info,
                docker_system_df,
                volumes,
            ) = await asyncio.gather(
                self.portainer.get_containers(endpoint.id),
                self.portainer.docker_version(endpoint.id),
                self.portainer.docker_info(endpoint.id),
                self.portainer.docker_system_df(endpoint.id, verbose=True),
                self.portainer.get_volumes(endpoint.id),
            )

            stack_requests = [self.portainer.get_stacks(endpoint_id=endpoint.id)]
            swarm_id = (
                docker_info.swarm.cluster.get("ID")
                if docker_info.swarm
                and docker_info.swarm.control_available
                and docker_info.swarm.cluster
                else None
            )
            if swarm_id:
                stack_requests.append(
                    self.portainer.get_stacks(
                        endpoint_id=endpoint.id, swarm_id=swarm_id
                    )
                )

            stacks = [
                stack
                for result in await asyncio.gather(*stack_requests)
                for stack in result
            ]

            prev_endpoint = self.data.get(endpoint.id) if self.data else None
            container_map: dict[str, PortainerContainerData] = {}
            stack_map: dict[str, PortainerStackData] = {
                stack.name: PortainerStackData(stack=stack, container_count=0)
                for stack in stacks
            }

            container_names = [
                sanitize_container_name(container.names[0]) for container in containers
            ]
            container_inspects = dict(
                zip(
                    container_names,
                    await asyncio.gather(
                        *(
                            self.portainer.inspect_container(endpoint.id, container.id)
                            for container in containers
                        )
                    ),
                    strict=False,
                )
            )
            local_images = dict(
                zip(
                    container_inspects,
                    await asyncio.gather(
                        *(
                            self._get_local_image(
                                endpoint.id, str(container_inspect.image)
                            )
                            for container_inspect in container_inspects.values()
                        )
                    ),
                    strict=False,
                )
            )

            # Map containers, started and stopped
            for container in containers:
                container_name = sanitize_container_name(container.names[0])
                prev_container = (
                    prev_endpoint.containers.get(container_name)
                    if prev_endpoint
                    else None
                )

                container_inspect = container_inspects[container_name]
                local_image = local_images[container_name]

                image_status = (
                    (
                        result.status
                        if (
                            result := self.watcher.results.get(
                                (endpoint.id, container.id)
                            )
                        )
                        else None
                    )
                    if self.watcher
                    else None
                )

                # Check if container belongs to a stack via docker compose label
                stack_name: str | None = (
                    container.labels.get("com.docker.compose.project")
                    or container.labels.get("com.docker.stack.namespace")
                    if container.labels
                    else None
                )
                if stack_name and (stack_data := stack_map.get(stack_name)):
                    stack_data.container_count += 1

                container_map[container_name] = PortainerContainerData(
                    container=container,
                    container_inspect=container_inspect,
                    local_image=local_image,
                    stats=None,
                    stats_pre=prev_container.stats if prev_container else None,
                    image_status=image_status,
                    stack=stack_map[stack_name].stack
                    if stack_name and stack_name in stack_map
                    else None,
                )

            volume_usage_map = {
                item["Name"]: item
                for item in (docker_system_df.volume_disk_usage.items or [])
            }
            volume_map: dict[str, PortainerVolumeData] = {}
            for volume in volumes:
                if item := volume_usage_map.get(volume.name):
                    volume.usage_data = DockerVolumeUsageData(
                        size=item["UsageData"]["Size"],
                        ref_count=item["UsageData"]["RefCount"],
                    )
                volume_map[volume.name] = PortainerVolumeData(volume=volume)

            # Separately fetch stats for active containers
            active_containers = [
                container
                for container in containers
                if container.state
                in (DockerContainerState.RUNNING, DockerContainerState.PAUSED)
            ]
            if active_containers:
                container_stats = dict(
                    zip(
                        (
                            sanitize_container_name(container.names[0])
                            for container in active_containers
                        ),
                        await asyncio.gather(
                            *(
                                self.portainer.container_stats(
                                    endpoint_id=endpoint.id,
                                    container_id=container.id,
                                )
                                for container in active_containers
                            )
                        ),
                        strict=False,
                    )
                )

                # Now assign stats to the containers
                for container_name, stats in container_stats.items():
                    container_map[container_name].stats = stats

            mapped_endpoints[endpoint.id] = PortainerCoordinatorData(
                id=endpoint.id,
                name=endpoint.name,
                endpoint=endpoint,
                containers=container_map,
                docker_version=docker_version,
                docker_info=docker_info,
                volumes=volume_map,
                stacks=stack_map,
            )

        self._async_add_remove_endpoints(mapped_endpoints)

        return mapped_endpoints

    def _async_add_remove_endpoints(
        self, mapped_endpoints: dict[int, PortainerCoordinatorData]
    ) -> None:
        """Add new endpoints, remove non-existing endpoints."""
        current_endpoints = {endpoint.id for endpoint in mapped_endpoints.values()}
        self.known_endpoints &= current_endpoints
        new_endpoints = current_endpoints - self.known_endpoints
        if new_endpoints:
            _LOGGER.debug("New endpoints found: %s", new_endpoints)
            self.known_endpoints.update(new_endpoints)
            new_endpoint_data = [
                mapped_endpoints[endpoint_id] for endpoint_id in new_endpoints
            ]
            for endpoint_callback in self.new_endpoints_callbacks:
                endpoint_callback(new_endpoint_data)

        # Surprise, we also handle containers here :)
        current_containers = {
            (endpoint.id, container_name)
            for endpoint in mapped_endpoints.values()
            for container_name in endpoint.containers
        }
        # Prune departed containers so a recreated container is detected as new
        # and its entity is rebuilt with the fresh (ephemeral) Docker container ID.
        self.known_containers &= current_containers
        new_containers = current_containers - self.known_containers
        if new_containers:
            _LOGGER.debug("New containers found: %s", new_containers)
            self.known_containers.update(new_containers)
            new_container_data = [
                (
                    mapped_endpoints[endpoint_id],
                    mapped_endpoints[endpoint_id].containers[name],
                )
                for endpoint_id, name in new_containers
            ]
            for container_callback in self.new_containers_callbacks:
                container_callback(new_container_data)

        # Volume management
        current_volumes = {
            (endpoint.id, volume_name)
            for endpoint in mapped_endpoints.values()
            for volume_name in endpoint.volumes
        }

        self.known_volumes &= current_volumes
        new_volumes = current_volumes - self.known_volumes
        if new_volumes:
            _LOGGER.debug("New volumes found: %s", new_volumes)
            self.known_volumes.update(new_volumes)
            new_volume_data = [
                (
                    mapped_endpoints[endpoint_id],
                    mapped_endpoints[endpoint_id].volumes[name],
                )
                for endpoint_id, name in new_volumes
            ]
            for volume_callback in self.new_volumes_callbacks:
                volume_callback(new_volume_data)

        # Stack management
        current_stacks = {
            (endpoint.id, stack_name)
            for endpoint in mapped_endpoints.values()
            for stack_name in endpoint.stacks
        }

        self.known_stacks &= current_stacks
        new_stacks = current_stacks - self.known_stacks
        if new_stacks:
            _LOGGER.debug("New stacks found: %s", new_stacks)
            self.known_stacks.update(new_stacks)
            new_stack_data = [
                (
                    mapped_endpoints[endpoint_id],
                    mapped_endpoints[endpoint_id].stacks[name],
                )
                for endpoint_id, name in new_stacks
            ]
            for stack_callback in self.new_stacks_callbacks:
                stack_callback(new_stack_data)

    async def _get_local_image(
        self, endpoint_id: int, image: str
    ) -> LocalImageInformation:
        """Fetch local image data, reusing the cache until the watcher checks again."""
        if cached := self._image_cache.get((endpoint_id, image)):
            cached_at, local_image = cached
            if (
                self.watcher is None
                or self.watcher.last_check is None
                or cached_at >= self.watcher.last_check
            ):
                _LOGGER.debug(
                    "Using cached local image for endpoint %d, image %s",
                    endpoint_id,
                    image,
                )
                return local_image

        local_image = await self.portainer.get_image(endpoint_id, image)
        self._image_cache[(endpoint_id, image)] = (
            time.monotonic(),
            local_image,
        )
        return local_image


class PortainerDockerDiskSpaceCoordinator(
    PortainerBaseCoordinator[dict[int, DockerSystemDF]]
):
    """Data Update Coordinator for Docker disk space."""

    config_entry: PortainerConfigEntry
    _update_interval = DEFAULT_DF_SCAN_INTERVAL

    @override
    async def update_data(self) -> dict[int, DockerSystemDF]:
        """Fetch Docker disk space data independently from Portainer API."""
        endpoints = await self.portainer.get_endpoints()
        results: dict[int, DockerSystemDF] = {}
        for endpoint in endpoints:
            if endpoint.status == EndpointStatus.DOWN:
                continue
            results[endpoint.id] = await self.portainer.docker_system_df(endpoint.id)
        return results
