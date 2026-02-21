"""AirOS button component for Home Assistant."""

from __future__ import annotations

import logging

from airos.exceptions import AirOSDataMissingError, AirOSDeviceConnectionError

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import AirOSConfigEntry, AirOSDataUpdateCoordinator
from .entity import AirOSEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

BUTTON_DESCRIPTION = ButtonEntityDescription(
    key="reboot",
    device_class=ButtonDeviceClass.RESTART,
    translation_key="reboot_device",
    entity_registry_enabled_default=False,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AirOSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the AirOS button from a config entry."""
    async_add_entities(
        [AirOSRebootButton(config_entry.runtime_data)], update_before_add=False
    )


class AirOSRebootButton(AirOSEntity, ButtonEntity):
    """Button to reboot device."""

    _attr_has_entity_name = True
    _attr_device_class = ButtonDeviceClass.RESTART

    entity_description: ButtonEntityDescription

    def __init__(self, coordinator: AirOSDataUpdateCoordinator) -> None:
        """Initialize the AirOS client button."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entity_description = BUTTON_DESCRIPTION

        self._attr_unique_id = f"{coordinator.config_entry.unique_id}_reboot"

        self._attr_name = "Reboot Device"

    async def async_press(self) -> None:
        """Handle the button press to reboot the device."""
        result: bool = False
        try:
            await self.coordinator.airos_device.login()
            result = await self.coordinator.airos_device.reboot()

        except AirOSDataMissingError, AirOSDeviceConnectionError:
            _LOGGER.exception("Failed to reboot device")

        else:
            if not result:
                _LOGGER.error("Unable to reboot device")
