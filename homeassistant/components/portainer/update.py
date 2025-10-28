"""Platform for Portainer container update integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pyportainer.exceptions import (
    PortainerAuthenticationError,
    PortainerConnectionError,
)

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PortainerConfigEntry
from .const import CONTAINER_IMAGE, DOMAIN
from .coordinator import PortainerBeaconCoordinator
from .entity import PortainerContainerUpdateEntity


@dataclass(frozen=True)
class PortainerContainerUpdateEntityDescription(UpdateEntityDescription):
    """Describes Portainer container update entity."""

    latest_version: Callable[[], str]
    update_func: Callable[[], Awaitable[bool]]


UPDATE_TYPES: dict[str, PortainerContainerUpdateEntityDescription] = {
    CONTAINER_IMAGE: PortainerContainerUpdateEntityDescription(
        key="container_image_update",
        translation_key="container_image_update",
        device_class=UpdateDeviceClass.FIRMWARE,
        entity_category=EntityCategory.CONFIG,
        latest_version=lambda data: data.new_firmware_version.split("_")[0],
        update_func=lambda device: device.device.async_start_firmware_update(),  # type: ignore[union-attr]
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PortainerConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Get all devices and sensors and setup them via config entry."""
    coordinator = entry.runtime_data.coordinator

    async_add_entities(
        [
            PortainerContainerUpdateEntity(
                entry,
                coordinator[CONTAINER_IMAGE],
                UPDATE_TYPES[CONTAINER_IMAGE],
            )
        ]
    )


class PortainerContainerUpdateEntity(PortainerContainerUpdateEntity, UpdateEntity):
    """Representation of a Portainer container update."""

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )

    entity_description: PortainerContainerUpdateEntityDescription

    def __init__(
        self,
        entry: PortainerConfigEntry,
        coordinator: PortainerBeaconCoordinator,
        description: PortainerContainerUpdateEntityDescription,
    ) -> None:
        """Initialize entity."""
        self.entity_description = description
        super().__init__(entry, coordinator)
        self._in_progress_old_version: str | None = None

    @property
    def installed_version(self) -> str:
        """Version currently in use."""
        return self.device.firmware_version

    @property
    def latest_version(self) -> str:
        """Latest version available for install."""
        if latest_version := self.entity_description.latest_version(
            self.coordinator.data
        ):
            return latest_version
        return self.device.firmware_version

    @property
    def in_progress(self) -> bool:
        """Update installation in progress."""
        return self._in_progress_old_version == self.installed_version

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Turn the entity on."""
        self._in_progress_old_version = self.installed_version
        try:
            await self.entity_description.update_func(self.device)
        except PortainerAuthenticationError as ex:
            self.entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="invalid_auth",
                translation_placeholders={"title": self.entry.title},
            ) from ex
        except PortainerConnectionError as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
                translation_placeholders={"title": self.entry.title},
            ) from ex
