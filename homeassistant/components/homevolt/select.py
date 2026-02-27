"""Support for Homevolt select entities."""

from __future__ import annotations

from homevolt.const import SCHEDULE_TYPE

from homeassistant.components.select import SelectEntity
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
    """Set up Homevolt select entities."""
    coordinator = entry.runtime_data
    async_add_entities([HomevoltModeSelect(coordinator)])


class HomevoltModeSelect(HomevoltEntity, SelectEntity):
    """Select entity for battery operational mode."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "battery_mode"
    _attr_options = list(SCHEDULE_TYPE.values())

    def __init__(self, coordinator: HomevoltDataUpdateCoordinator) -> None:
        """Initialize the select entity."""
        self._attr_unique_id = f"{coordinator.data.unique_id}_battery_mode"
        device_id = coordinator.data.unique_id
        super().__init__(coordinator, f"ems_{device_id}")

    @property
    def current_option(self) -> str | None:
        """Return the current selected mode."""
        mode_int = self.coordinator.client.schedule_mode
        return SCHEDULE_TYPE.get(mode_int)

    @homevolt_exception_handler
    async def async_select_option(self, option: str) -> None:
        """Change the selected mode."""
        await self.coordinator.client.set_battery_mode(mode=option)
        await self.coordinator.async_request_refresh()
