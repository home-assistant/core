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

from . import MyPVConfigEntry
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

    @property
    @override
    def installed_version(self) -> str | None:
        """Version installed and in use."""
        return self.coordinator.device.firmware_version

    @property
    @override
    def latest_version(self) -> str | None:
        """Latest version available for install."""
        return self.coordinator.device.latest_firmware_version

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

    @property
    @override
    def has_update(self) -> bool:
        """Return True if there is an update available."""
        return self.coordinator.device.firmware_update_available

    @override
    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()

        self._update_progress()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_progress()
        super()._handle_coordinator_update()

    @callback
    def _update_progress(self) -> None:
        """Update the firmware update progress from the device."""
        if (
            update_progress := self.coordinator.device.firmware_update_progress
        ) is not None:
            self._attr_in_progress = True
            self._attr_update_percentage = update_progress
        else:
            self._attr_in_progress = False
            self._attr_update_percentage = None
