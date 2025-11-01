"""Support for Portainer container updates."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from pyportainer import Portainer
from pyportainer.exceptions import (
    PortainerAuthenticationError,
    PortainerConnectionError,
)
from pyportainer.models.docker import ImageInformation

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


@dataclass(frozen=True, kw_only=True)
class PortainerContainerUpdateEntityDescription(UpdateEntityDescription):
    """Describes Portainer container update entity."""

    latest_version: Callable[[ImageInformation], str | None]
    update_func: Callable[
        [Portainer, int, str, str | None],
        Coroutine[Any, Any, None],
    ]
    display_precision: int = 0


DEFAULT_RECREATE_TIMEOUT = timedelta(minutes=10)


CONTAINER_IMAGE: tuple[PortainerContainerUpdateEntityDescription] = (
    PortainerContainerUpdateEntityDescription(
        key="container_image_update",
        translation_key="container_image_update",
        device_class=UpdateDeviceClass.FIRMWARE,
        entity_category=EntityCategory.CONFIG,
        latest_version=lambda data: (
            data.descriptor.digest
            if (data.descriptor and data.descriptor.digest)
            else None
        ),
        update_func=(
            lambda portainer,
            endpoint_id,
            container_id,
            image: portainer.container_recreate_helper(
                endpoint_id, container_id, str(image), DEFAULT_RECREATE_TIMEOUT
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

    async_add_entities(
        PortainerContainerImageUpdateEntity(
            beacon,
            endpoint,
            container,
            entity_description,
        )
        for endpoint in beacon.data.values()
        for container in endpoint.containers.values()
        for entity_description in CONTAINER_IMAGE
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
    def installed_version(self) -> str | None:
        """Return installed version."""
        return (
            self.coordinator.data[self.endpoint.id]
            .containers[self.device_name]
            .container_inspect.image
        )

    @property
    def latest_version(self) -> str | None:
        """Return latest version."""
        container = self.coordinator.data[self.endpoint.id].containers[self.device_name]
        return self.entity_description.latest_version(container.image_info)

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
                self.endpoint.id,
                self.container.core.id,
                self.latest_version,
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
