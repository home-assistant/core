# pylint: disable=duplicate-code
"""Creates Button entities for the my-PV Home Assistant integration."""

import logging

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import MyPVCoordinator

_LOGGER = logging.getLogger(__name__)


BUTTON_DESCRIPTIONS = {
    "reboot_device": ButtonEntityDescription(
        key="reboot_device",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.DIAGNOSTIC,
    )
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the my-PV button."""
    coordinator: MyPVCoordinator = config_entry.runtime_data
    entities = []

    for command, configuration in coordinator.command_configurations:
        if (
            configuration.get("type")
            in [
                "any",
                "fixed",
            ]
        ) and (entity_description := BUTTON_DESCRIPTIONS.get(command)):
            entities.append(
                MyPVCommandButton(
                    coordinator,
                    entity_description,
                    config_entry.entry_id,
                )
            )

    async_add_entities(entities)


class MyPVCommandButton(CoordinatorEntity, ButtonEntity):
    """Base my-PV Button."""

    _attr_has_entity_name = True
    _attr_available = False

    coordinator: MyPVCoordinator

    def __init__(
        self,
        coordinator: MyPVCoordinator,
        entity_description: ButtonEntityDescription,
        config_entry_id: str,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, entity_description.key)

        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{config_entry_id}-{entity_description.key}"

        self.entity_description = entity_description

    async def async_added_to_hass(self) -> None:
        """Called when entity is added to Home Assistant."""
        await super().async_added_to_hass()

        self._handle_coordinator_update()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self._attr_available:
            return self._attr_available

        return self.coordinator.last_update_success

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.connected:
            self._attr_available = False
        else:
            self._attr_available = True

        self.async_write_ha_state()

    async def async_press(self, **kwargs) -> None:
        """Handle the button press."""
        _LOGGER.debug("Pressing %s", self.name)

        if not self.coordinator.connected:
            self._attr_available = False
        elif await self.coordinator.send_command(self.entity_description.key):
            self._attr_available = True
        else:
            _LOGGER.error("Failed to press %s", self.name)

        self.async_write_ha_state()
