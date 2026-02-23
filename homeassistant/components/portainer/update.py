"""Support for Portainer container updates."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from pyportainer import Portainer
from pyportainer.exceptions import (
    PortainerAuthenticationError,
    PortainerConnectionError,
)
from pyportainer.models.docker import (
    DockerContainer,
    LocalImageInformation,
    PortainerImageUpdateStatus,
)

from homeassistant.components.update import (
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import (
    PortainerConfigEntry,
    PortainerContainerData,
    PortainerCoordinator,
    PortainerCoordinatorData,
)
from .entity import PortainerContainerEntity


@dataclass(frozen=True, kw_only=True)
class PortainerContainerUpdateEntityDescription(UpdateEntityDescription):
    """Describes Portainer container update entity."""

    installed_version: Callable[[LocalImageInformation], str | None]
    latest_version: Callable[[PortainerImageUpdateStatus | None], str | None]
    update_func: Callable[
        [Portainer, int, str],
        Awaitable[DockerContainer],
    ]


PARALLEL_UPDATES = 1
DEFAULT_RECREATE_TIMEOUT = timedelta(minutes=10)


CONTAINER_IMAGE: tuple[PortainerContainerUpdateEntityDescription] = (
    PortainerContainerUpdateEntityDescription(
        key="container_image_update",
        translation_key="container_image_update",
        entity_category=EntityCategory.CONFIG,
        installed_version=lambda data: (
            data.repo_digests[0].split("@")[1]
            if data.repo_digests and isinstance(data.repo_digests[0], str)
            else None
        ),
        latest_version=lambda data: data.registry_digest if data is not None else None,
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
    entry: PortainerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Portainer update entities based on a config entry."""
    coordinator = entry.runtime_data

    def _async_add_new_containers(
        containers: list[tuple[PortainerCoordinatorData, PortainerContainerData]],
    ) -> None:
        """Add new container update sensors."""

        async_add_entities(
            PortainerContainerImageUpdateEntity(
                coordinator,
                entity_description,
                container,
                endpoint,
            )
            for (endpoint, container) in containers
            for entity_description in CONTAINER_IMAGE
        )

    coordinator.new_containers_callbacks.append(_async_add_new_containers)
    _async_add_new_containers(
        [
            (endpoint, container)
            for endpoint in coordinator.data.values()
            for container in endpoint.containers.values()
        ]
    )


class PortainerContainerImageUpdateEntity(PortainerContainerEntity, UpdateEntity):
    """Representation of a Portainer container update."""

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )

    entity_description: PortainerContainerUpdateEntityDescription

    def __init__(
        self,
        coordinator: PortainerCoordinator,
        entity_description: PortainerContainerUpdateEntityDescription,
        device_info: PortainerContainerData,
        via_device: PortainerCoordinatorData,
    ) -> None:
        """Initialize the Portainer update switch."""
        self.entity_description = entity_description
        super().__init__(device_info, coordinator, via_device)

        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{self.device_name}_{entity_description.key}"
        self._in_progress_old_version: str | None = None

    @property
    def title(self) -> str | None:
        """Return title."""
        return self.device_name

    @property
    def installed_version(self) -> str | None:
        """Return installed version."""
        return self.entity_description.installed_version(
            self.container_data.local_image
        )

    @property
    def latest_version(self) -> str | None:
        """Return latest version."""
        return self.entity_description.latest_version(self.container_data.image_status)

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
            await self.entity_description.update_func(
                self.coordinator.portainer,
                self.endpoint_id,
                self.container_data.container.id,
            )
        except PortainerAuthenticationError as ex:
            self.coordinator.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_auth_no_details",
            ) from ex
        except PortainerConnectionError as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect_no_details",
            ) from ex
        else:
            await self.coordinator.async_request_refresh()
        finally:
            self._in_progress_old_version = None
