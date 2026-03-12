"""Support for Homevolt switch entities."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HomevoltConfigEntry, HomevoltDataUpdateCoordinator
from .entity import HomevoltEntity, homevolt_exception_handler

PARALLEL_UPDATES = 0  # Coordinator-based updates


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomevoltConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Homevolt switch entities."""
    coordinator = entry.runtime_data
    async_add_entities([HomevoltLocalModeSwitch(coordinator)])


class HomevoltLocalModeSwitch(HomevoltEntity, SwitchEntity):
    """Switch entity for Homevolt local mode."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "local_mode"

    def __init__(self, coordinator: HomevoltDataUpdateCoordinator) -> None:
        """Initialize the switch entity."""
        self._attr_unique_id = f"{coordinator.data.unique_id}_local_mode"
        device_id = coordinator.data.unique_id
        super().__init__(coordinator, f"ems_{device_id}")

    @property
    def is_on(self) -> bool:
        """Return true if local mode is enabled."""
        return self.coordinator.client.local_mode_enabled

    @homevolt_exception_handler
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable local mode."""
        await self.coordinator.client.enable_local_mode()
        await self.coordinator.async_request_refresh()

    @homevolt_exception_handler
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable local mode."""
        await self.coordinator.client.disable_local_mode()
        await self.coordinator.async_request_refresh()
