"""Plugwise Button component for Home Assistant."""

from __future__ import annotations

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import PlugwiseConfigEntry
from .const import GATEWAY_ID, REBOOT
from .coordinator import PlugwiseDataUpdateCoordinator
from .entity import PlugwiseEntity
from .util import plugwise_command

BUTTON_TYPES: tuple[ButtonEntityDescription, ...] = (
    ButtonEntityDescription(
        key=REBOOT,
        translation_key=REBOOT,
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlugwiseConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Plugwise buttons from a ConfigEntry."""
    coordinator = entry.runtime_data

    @callback
    def _add_entities() -> None:
        """Add Entities during init and runtime."""
        if not coordinator.new_devices:
            return

        gateway = coordinator.data.gateway
        async_add_entities(
            PlugwiseButtonEntity(coordinator, device_id, description)
            for device_id in coordinator.new_devices
            if device_id == gateway[GATEWAY_ID] and REBOOT in gateway
            for description in BUTTON_TYPES
        )

    _add_entities()
    entry.async_on_unload(coordinator.async_add_listener(_add_entities))


class PlugwiseButtonEntity(PlugwiseEntity, ButtonEntity):
    """Defines a Plugwise button."""

    entity_description: ButtonEntityDescription

    def __init__(
        self,
        coordinator: PlugwiseDataUpdateCoordinator,
        device_id: str,
        description: ButtonEntityDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, device_id)
        self.device_id = device_id
        self.entity_description = description
        self._attr_unique_id = f"{device_id}-{description.key}"

    @plugwise_command
    async def async_press(self) -> None:
        """Triggers the Plugwise button press service."""
        await self.coordinator.api.reboot_gateway()
