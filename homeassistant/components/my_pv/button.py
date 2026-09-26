# pylint: disable=duplicate-code
"""Creates Button entities for the my-PV Home Assistant integration."""

from typing import Any, override

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import MyPVConfigEntry
from .const import DOMAIN
from .entity import MyPVBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MyPVConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the my-PV button."""
    coordinator = config_entry.runtime_data
    entities = []

    config = coordinator.device.get_command_configuration("reboot_device")
    if config and config.get("type") in ["any", "fixed"]:
        entity_description = ButtonEntityDescription(
            key="reboot_device",
            device_class=ButtonDeviceClass.RESTART,
            entity_category=EntityCategory.DIAGNOSTIC,
        )
        entities.append(
            MyPVCommandButton(
                coordinator,
                entity_description,
                coordinator.device.serial_number,
            )
        )

    async_add_entities(entities)


class MyPVCommandButton(MyPVBaseEntity, ButtonEntity):
    """Base my-PV Button."""

    @override
    async def async_press(self, **kwargs: Any) -> None:
        """Handle the button press."""

        if not await self.coordinator.send_command(self.entity_description.key):
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="unknown_error"
            )
