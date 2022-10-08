"""Update entities for Netgear devices."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, KEY_COORDINATOR_FIRMWARE, KEY_ROUTER
from .router import NetgearRouter, NetgearRouterCoordinatorEntity

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up update entities for Netgear component."""
    router = hass.data[DOMAIN][entry.entry_id][KEY_ROUTER]
    coordinator = hass.data[DOMAIN][entry.entry_id][KEY_COORDINATOR_FIRMWARE]
    entities = [NetgearUpdateEntity(coordinator, router)]

    async_add_entities(entities)


class NetgearUpdateEntity(NetgearRouterCoordinatorEntity, UpdateEntity):
    """Update entity for a Netgear device."""

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_supported_features = UpdateEntityFeature.INSTALL

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        router: NetgearRouter,
    ) -> None:
        """Initialize a Netgear device."""
        super().__init__(coordinator, router)
        self._name = f"{router.device_name} Update"
        self._unique_id = f"{router.serial_number}-update"

    @property
    def installed_version(self) -> str | None:
        """Version currently in use."""
        if self.coordinator.data is not None:
            return self.coordinator.data.get("CurrentVersion")
        return None

    @property
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        if self.coordinator.data is not None:
            new_version = self.coordinator.data.get("NewVersion")
            if new_version is not None and not new_version.startswith(
                self.installed_version
            ):
                return new_version
        return self.installed_version

    @property
    def release_summary(self) -> str | None:
        """Release summary."""
        if self.coordinator.data is not None:
            return self.coordinator.data.get("ReleaseNote")
        return None

    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install the latest firmware version."""
        await self._router.async_update_new_firmware()

    @callback
    def async_update_device(self) -> None:
        """Update the Netgear device."""
