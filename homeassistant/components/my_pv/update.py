"""Creates Update entities for the my-PV Home Assistant integration."""

import logging
from typing import Any, override

from homeassistant.components.update import (
    UpdateDeviceClass,
    UpdateEntity,
    UpdateEntityDescription,
    UpdateEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MyPVConfigEntry, MyPVCoordinator
from .const import DOMAIN
from .entity import MyPVBaseEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MyPVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the my-PV update."""
    coordinator = config_entry.runtime_data
    entities = []

    if (
        coordinator.device.firmware_version
        and coordinator.device.latest_firmware_version
    ):
        entity_description = UpdateEntityDescription(
            key="firmware_update",
            device_class=UpdateDeviceClass.FIRMWARE,
        )
        entities.append(
            MyPVFirmwareUpdate(
                coordinator,
                entity_description,
                coordinator.device.serial_number,
            )
        )

    async_add_entities(entities)


class MyPVFirmwareUpdate(MyPVBaseEntity, UpdateEntity):
    """Base my-PV Update."""

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.PROGRESS
    )

    def __init__(
        self,
        coordinator: MyPVCoordinator,
        entity_description: UpdateEntityDescription,
        serial_number: str,
    ) -> None:
        """Initialize the update."""
        super().__init__(coordinator, entity_description, serial_number)

        self._attr_installed_version = self.coordinator.device.firmware_version
        self._attr_latest_version = self.coordinator.device.latest_firmware_version

    @override
    async def async_install(
        self, version: str | None, backup: bool, **kwargs: Any
    ) -> None:
        """Install an update."""
        self._attr_in_progress = True
        self._attr_update_percentage = 0
        self.async_write_ha_state()

        if not await self.coordinator.update_firmware():
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="unknown_error"
            )

        self._attr_in_progress = False
        self._attr_update_percentage = None
        self.async_write_ha_state()

    @override
    def version_is_newer(self, latest_version: str, installed_version: str) -> bool:
        """Return True if latest_version is newer than installed_version."""
        return self.coordinator.device.firmware_update_available

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._attr_installed_version = self.coordinator.device.firmware_version
        self._attr_latest_version = self.coordinator.device.latest_firmware_version

        if (
            update_progress := self.coordinator.device.firmware_update_progress
        ) is not None:
            self._attr_in_progress = True
            self._attr_update_percentage = update_progress
        else:
            self._attr_in_progress = False
            self._attr_update_percentage = None

        self.async_write_ha_state()
