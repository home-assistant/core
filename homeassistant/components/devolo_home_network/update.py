"""Platform for update integration."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from devolo_plc_api.device import Device
from devolo_plc_api.device_api import UpdateFirmwareCheck
from devolo_plc_api.exceptions.device import DevicePasswordProtected, DeviceUnavailable

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
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, REGULAR_FIRMWARE
from .entity import DevoloCoordinatorEntity


@dataclass(frozen=True)
class DevoloUpdateRequiredKeysMixin:
    """Mixin for required keys."""

    latest_version: Callable[[UpdateFirmwareCheck], str]
    update_func: Callable[[Device], Awaitable[bool]]


@dataclass(frozen=True)
class DevoloUpdateEntityDescription(
    UpdateEntityDescription, DevoloUpdateRequiredKeysMixin
):
    """Describes devolo update entity."""


UPDATE_TYPES: dict[str, DevoloUpdateEntityDescription] = {
    REGULAR_FIRMWARE: DevoloUpdateEntityDescription(
        key=REGULAR_FIRMWARE,
        device_class=UpdateDeviceClass.FIRMWARE,
        entity_category=EntityCategory.CONFIG,
        latest_version=lambda data: data.new_firmware_version.split("_")[0],
        update_func=lambda device: device.device.async_start_firmware_update(),  # type: ignore[union-attr]
    ),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Get all devices and sensors and setup them via config entry."""
    device: Device = hass.data[DOMAIN][entry.entry_id]["device"]
    coordinators: dict[str, DataUpdateCoordinator[Any]] = hass.data[DOMAIN][
        entry.entry_id
    ]["coordinators"]

    async_add_entities(
        [
            DevoloUpdateEntity(
                entry,
                coordinators[REGULAR_FIRMWARE],
                UPDATE_TYPES[REGULAR_FIRMWARE],
                device,
            )
        ]
    )


class DevoloUpdateEntity(DevoloCoordinatorEntity, UpdateEntity):
    """Representation of a devolo update."""

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )

    entity_description: DevoloUpdateEntityDescription

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: DataUpdateCoordinator,
        description: DevoloUpdateEntityDescription,
        device: Device,
    ) -> None:
        """Initialize entity."""
        self.entity_description = description
        super().__init__(entry, coordinator, device)
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
        except DevicePasswordProtected as ex:
            self.entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                f"Device {self.entry.title} require re-authentication to set or change the password"
            ) from ex
        except DeviceUnavailable as ex:
            raise HomeAssistantError(
                f"Device {self.entry.title} did not respond"
            ) from ex
