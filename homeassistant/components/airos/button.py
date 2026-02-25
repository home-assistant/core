"""AirOS button component for Home Assistant."""

from __future__ import annotations

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

PARALLEL_UPDATES = 0

REBOOT_BUTTON = ButtonEntityDescription(
    key="reboot",
    device_class=ButtonDeviceClass.RESTART,
    entity_registry_enabled_default=False,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AirOSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the AirOS button from a config entry."""
    async_add_entities([AirOSRebootButton(config_entry.runtime_data, REBOOT_BUTTON)])


class AirOSRebootButton(AirOSEntity, ButtonEntity):
    """Button to reboot device."""

    entity_description: ButtonEntityDescription

    def __init__(
        self,
        coordinator: AirOSDataUpdateCoordinator,
        description: ButtonEntityDescription,
    ) -> None:
        """Initialize the AirOS client button."""
        super().__init__(coordinator)

        self.entity_description = description
        self._attr_unique_id = f"{coordinator.data.derived.mac}_{description.key}"

    async def async_press(self) -> None:
        """Handle the button press to reboot the device."""
        try:
            await self.coordinator.airos_device.login()
            result = await self.coordinator.airos_device.reboot()

        except AirOSException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err

        if not result:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="reboot_failed",
            ) from None
