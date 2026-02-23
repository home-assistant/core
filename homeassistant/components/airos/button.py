"""AirOS button component for Home Assistant."""

from __future__ import annotations

import logging

from airos.exceptions import AirOSException

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DOMAIN, AirOSConfigEntry, AirOSDataUpdateCoordinator
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
    async_add_entities([AirOSRebootButton(config_entry.runtime_data)])


class AirOSRebootButton(AirOSEntity, ButtonEntity):
    """Button to reboot device."""

    entity_description: ButtonEntityDescription

    def __init__(self, coordinator: AirOSDataUpdateCoordinator, entity_description: ButtonEntityDescription) -> None:
        """Initialize the AirOS client button."""
        super().__init__(coordinator)
        self.entity_description = ButtonEntityDescription

        self._attr_unique_id = f"{coordinator.data.derived.mac}_{entity_description.key}"

    async def async_press(self) -> None:
        """Handle the button press to reboot the device."""
        try:
            await self.coordinator.airos_device.login()
            result = await self.coordinator.airos_device.reboot()

        except AirOSException as err:
            _LOGGER.exception("Failed to send reboot request to device")
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err
        else:
            if not result:
                _LOGGER.error("Device indicates it failed to initiate reboot")
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="reboot_failed",
                ) from None
