"""Support for SwitchBot event entities."""

from __future__ import annotations

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SwitchbotConfigEntry, SwitchbotDataUpdateCoordinator
from .entity import SwitchbotEntity

PARALLEL_UPDATES = 0

EVENT_TYPES = {
    "doorbell": EventEntityDescription(
        key="doorbell",
        device_class=EventDeviceClass.DOORBELL,
        event_types=["ring"],
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SwitchbotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SwitchBot event platform."""
    coordinator = config_entry.runtime_data
    event_entities: list[EventEntity] = []
    event_entities.extend(
        SwitchbotEventEntity(coordinator, event)
        for event in coordinator.device.parsed_data
        if event in EVENT_TYPES
    )
    async_add_entities(event_entities)


class SwitchbotEventEntity(SwitchbotEntity, EventEntity):
    """Representation of a SwitchBot event."""

    def __init__(
        self,
        coordinator: SwitchbotDataUpdateCoordinator,
        event: str,
    ) -> None:
        """Initialize the SwitchBot event."""
        super().__init__(coordinator)
        self._event = event
        self.entity_description = EVENT_TYPES[event]
        self._attr_unique_id = f"{coordinator.base_unique_id}-{event}"
        self._previous_value = False

    @callback
    def _async_update_attrs(self) -> None:
        """Update the entity attributes."""
        value = bool(self.parsed_data.get(self._event, False))
        if value and not self._previous_value:
            self._trigger_event("ring")
        self._previous_value = value
