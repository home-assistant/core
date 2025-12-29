"""Support for Portainer container updates."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from pyportainer import Portainer
from pyportainer.exceptions import (
    PortainerAuthenticationError,
    PortainerConnectionError,
)
from pyportainer.models.docker import DockerContainer, LocalImageInformation

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import (
    ContainerBeaconData,
    PortainerBeaconCoordinator,
    PortainerBeaconData,
)
from .entity import PortainerContainerUpdateEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class PortainerContainerUpdateEntityDescription(UpdateEntityDescription):
    """Describes Portainer container update entity."""

    latest_version: Callable[[LocalImageInformation], str | None]
    update_func: Callable[
        [Portainer, int, str],
        Awaitable[DockerContainer],
    ]
    display_precision: int = 0


# Don't overload Portainer API with too many parallel updates
PARALLEL_UPDATES = 3
DEFAULT_RECREATE_TIMEOUT = timedelta(minutes=10)


CONTAINER_IMAGE: tuple[PortainerContainerUpdateEntityDescription] = (
    PortainerContainerUpdateEntityDescription(
        key="container_image_update",
        translation_key="container_image_update",
        device_class=UpdateDeviceClass.FIRMWARE,  # @TODO: find a better device class. Let's await the review.
        entity_category=EntityCategory.CONFIG,
        latest_version=lambda data: (
            data.repo_digests[0].split("@")[1] if data.repo_digests else None
        ),
        update_func=(
            lambda portainer, endpoint_id, container_id: portainer.container_recreate(
                endpoint_id=endpoint_id,
                container_id=container_id,
                timeout=DEFAULT_RECREATE_TIMEOUT,
                pull_image=True,
            )
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Portainer update entities based on a config entry."""
    beacon = entry.runtime_data.beacon
    coordinator = entry.runtime_data.coordinator

    def _async_add_new_containers(
        containers: list[tuple[PortainerBeaconData, ContainerBeaconData]],
    ) -> None:
        """Add new container update sensors."""

        async_add_entities(
            PortainerContainerImageUpdateEntity(
                beacon,
                endpoint,
                container,
                entity_description,
            )
            for (endpoint, container) in containers
            for entity_description in CONTAINER_IMAGE
        )

    coordinator.new_containers_callbacks.append(_async_add_new_containers)
    _async_add_new_containers(
        [
            (endpoint, container)
            for endpoint in beacon.data.values()
            for container in endpoint.containers.values()
        ]
    )


class PortainerContainerImageUpdateEntity(PortainerContainerUpdateEntity, UpdateEntity):
    """Representation of a Portainer container update."""

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )

    entity_description: PortainerContainerUpdateEntityDescription

    def __init__(
        self,
        coordinator: PortainerBeaconCoordinator,
        endpoint: PortainerBeaconData,
        container: ContainerBeaconData,
        entity_description: PortainerContainerUpdateEntityDescription,
    ) -> None:
        """Initialize entity."""
        self.entity_description = entity_description
        super().__init__(coordinator, endpoint, container)

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self.endpoint.id}_{self.device_name}_{entity_description.key}"
        self._in_progress_old_version: str | None = None

    @property
    def title(self) -> str | None:
        """Return title."""
        name = (
            self.coordinator.data[self.endpoint.id]
            .containers[self.device_name]
            .container_inspect.name
        )
        assert name
        return name.strip("/")

    @property
    def installed_version(self) -> str | None:
        """Return installed version."""
        return self.container.new_digest

    @property
    def latest_version(self) -> str | None:
        """Return latest version."""
        return self.entity_description.latest_version(self.container.local_image)

    @property
    def in_progress(self) -> bool:
        """Return if an update is in progress."""
        return self._in_progress_old_version == self.installed_version

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install update."""
        self._in_progress_old_version = self.installed_version
        try:
            _LOGGER.debug(
                "Starting update for container %s on endpoint %s",
                self.device_name,
                self.endpoint.name,
            )
            await self.entity_description.update_func(
                self.coordinator.portainer,
                self.endpoint.id,
                self.container.core.id,
            )
        except PortainerAuthenticationError as ex:
            self.coordinator.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
                translation_placeholders={"title": self.coordinator.config_entry.title},
            ) from ex
        except PortainerConnectionError as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"title": self.coordinator.config_entry.title},
            ) from ex
        else:
            _LOGGER.debug(
                "Successfully updated container %s on endpoint %s",
                self.device_name,
                self.endpoint.name,
            )
            self._in_progress_old_version = None
            await self.coordinator.async_request_refresh()
