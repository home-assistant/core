"""Support for WLED updates."""
from __future__ import annotations

from typing import Any

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .hub import MikrotikDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Mikrotik hub update entity."""
    coordinator: MikrotikDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MikrotikUpdateEntity(coordinator)])


class MikrotikUpdateEntity(
    CoordinatorEntity[MikrotikDataUpdateCoordinator], UpdateEntity
):
    """Defines a Mikrotik update entity."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = UpdateEntityFeature.INSTALL
    _attr_has_entity_name = True

    def __init__(self, coordinator: MikrotikDataUpdateCoordinator) -> None:
        """Initialize the update entity."""
        super().__init__(coordinator)
        self._attr_name = "Firmware"
        self._attr_title = self.coordinator.model
        self._attr_unique_id = f"{coordinator.serial_num}-firmware-update"
        self._attr_device_info = DeviceInfo(
            connections={(DOMAIN, coordinator.serial_num)},
            name=self.coordinator.hostname,
        )

    @property
    def installed_version(self) -> str | None:
        """Version currently installed and in use."""
        return self.coordinator.api.installed_version

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        return self.coordinator.api.latest_version

    @property
    def release_url(self) -> str | None:
        """URL to the changelogs of the latest version available."""
        return "https://mikrotik.com/download/changelogs"

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        await self.hass.async_add_executor_job(self.coordinator.api.install_update)
