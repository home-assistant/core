"""Text platform for Besen BS20."""

from typing import override

from homeassistant.components.text import TextEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BesenBS20ConfigEntry
from .coordinator import BesenBS20Coordinator
from .entity import BesenBS20Entity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BesenBS20ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Besen BS20 text entities."""

    async_add_entities([BesenBS20NameText(entry.runtime_data.coordinator)])


class BesenBS20NameText(BesenBS20Entity, TextEntity):
    """Charger device name text entity."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min = 1
    _attr_native_max = 11

    def __init__(self, coordinator: BesenBS20Coordinator) -> None:
        """Initialize the text entity."""

        super().__init__(coordinator, "device_name")

    @property
    @override
    def native_value(self) -> str | None:
        """Return charger name."""

        data = self.coordinator.data or self.coordinator.client.state
        return data.config.device_name

    @override
    async def async_set_value(self, value: str) -> None:
        """Set charger name."""

        await self.coordinator.async_set_device_name(value)
