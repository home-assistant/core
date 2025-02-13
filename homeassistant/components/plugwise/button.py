"""Plugwise Button component for Home Assistant."""

from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import REBOOT
from .coordinator import PlugwiseConfigEntry, PlugwiseDataUpdateCoordinator
from .entity import PlugwiseEntity
from .util import plugwise_command

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PlugwiseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Plugwise buttons from a ConfigEntry."""
    coordinator = entry.runtime_data

    async_add_entities(
        PlugwiseButtonEntity(coordinator, device_id)
        for device_id in coordinator.data
        if device_id == coordinator.api.gateway_id and coordinator.api.reboot
    )


class PlugwiseButtonEntity(PlugwiseEntity, ButtonEntity):
    """Defines a Plugwise button."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: PlugwiseDataUpdateCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, device_id)
        self._attr_translation_key = REBOOT
        self._attr_unique_id = f"{device_id}-reboot"

    @plugwise_command
    async def async_press(self) -> None:
        """Triggers the Plugwise button press service."""
        await self.coordinator.api.reboot_gateway()
