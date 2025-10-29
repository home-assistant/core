"""Data Update Coordinator for Portainer."""

from __future__ import annotations

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
    ImageInformation,
    ImageManifestDescriptor,
)
from pyportainer.models.docker_inspect import DockerInfo, DockerInspect, DockerVersion
from pyportainer.models.portainer import Endpoint

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
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
    containers: dict[str, DockerContainer]
    docker_version: DockerVersion
    docker_info: DockerInfo


@dataclass(slots=True, kw_only=True)
class ContainerBeaconData:
    """Data class for Container Beacon Data."""

    core: DockerContainer
    image_info: ImageInformation
    container_inspect: DockerInspect
    old_digest: str
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
            Callable[[list[tuple[PortainerCoordinatorData, DockerContainer]]], None]
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
        else:
            _LOGGER.debug("Fetched endpoints: %s", endpoints)

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
                containers={
                    container.names[0].replace("/", " ").strip(): container
                    for container in containers
                },
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
            (endpoint.id, container.id)
            for endpoint in mapped_endpoints.values()
            for container in endpoint.containers.values()
        }
        new_containers = current_containers - self.known_containers
        if new_containers:
            _LOGGER.debug("New containers found: %s", new_containers)
            self.known_containers.update(new_containers)


class PortainerBeaconCoordinator(DataUpdateCoordinator):
    """Data Update Coordinator for Portainer periodic background tasks."""

    config_entry: PortainerConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: PortainerConfigEntry,
        portainer: Portainer,
    ) -> None:
        """Initialize the Portainer Beacon Data Update Coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=f"{DOMAIN}",
            update_interval=BEACON_SCAN_INTERVAL,
        )
        self.portainer = portainer

    async def _async_setup(self):
        _LOGGER.debug("Setting up Portainer Beacon Coordinator")
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

    async def _async_update_data(self):
        """Perform periodic background tasks."""
        _LOGGER.debug("Performing Portainer Beacon Coordinator background tasks")

        # Check for container image updates
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

        mapped_endpoints: dict[int, PortainerBeaconData] = {}
        for endpoint in endpoints:
            if endpoint.status == ENDPOINT_STATUS_DOWN:
                _LOGGER.debug(
                    "Skipping offline endpoint: %s (ID: %d)",
                    endpoint.name,
                    endpoint.id,
                )
                continue

            try:
                containers = await self.portainer.get_containers(
                    endpoint_id=endpoint.id
                )

                container_data: dict[str, ContainerBeaconData] = {}
                for container in containers:
                    # image_info = await self.portainer.get_image_information(
                    #     endpoint_id=endpoint.id, image_id=container.image
                    # )
                    # @ERWIN: Silly local stub data
                    image_info = ImageInformation(
                        descriptor=ImageManifestDescriptor(
                            digest=f"sha256:stub-{container.id[:8]}"
                        )
                    )
                    container_inspect = await self.portainer.inspect_container(
                        endpoint_id=endpoint.id, container_id=container.id
                    )

                    if (
                        update_available := image_info.descriptor.digest
                        != container_inspect.image
                    ):
                        # TODO: works perfect for debugging. Can be refactored later on.
                        _LOGGER.debug(
                            "Container %s (ID: %s) on Endpoint %s (ID: %d) has an update available",
                            container.names[0],
                            container.id,
                            endpoint.name,
                            endpoint.id,
                        )

                    container_data[container.names[0].replace("/", " ").strip()] = (
                        ContainerBeaconData(
                            core=container,
                            image_info=image_info,
                            container_inspect=container_inspect,
                            old_digest=container_inspect.image,
                            new_digest=image_info.descriptor.digest,
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
                _LOGGER.exception("Authentication error")
                raise ConfigEntryAuthFailed(
                    translation_domain=DOMAIN,
                    translation_key="invalid_auth",
                    translation_placeholders={"error": repr(err)},
                ) from err
            _LOGGER.debug("Completed Portainer Beacon Coordinator background tasks")

            mapped_endpoints[endpoint.id] = PortainerBeaconData(
                id=endpoint.id,
                name=endpoint.name,
                endpoint=endpoint,
                containers=container_data,
            )

        return mapped_endpoints
