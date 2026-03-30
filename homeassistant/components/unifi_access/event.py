"""Event platform for the UniFi Access integration."""

from __future__ import annotations

from dataclasses import dataclass

from unifi_access_api import Door

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DoorEvent, UnifiAccessConfigEntry, UnifiAccessCoordinator
from .entity import UnifiAccessEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class UnifiAccessEventEntityDescription(EventEntityDescription):
    """Describes a UniFi Access event entity."""

    category: str


DOORBELL_EVENT_DESCRIPTION = UnifiAccessEventEntityDescription(
    key="doorbell",
    translation_key="doorbell",
    device_class=EventDeviceClass.DOORBELL,
    event_types=["ring"],
    category="doorbell",
)

ACCESS_EVENT_DESCRIPTION = UnifiAccessEventEntityDescription(
    key="access",
    translation_key="access",
    event_types=["access_granted", "access_denied"],
    category="access",
)

EVENT_DESCRIPTIONS: list[UnifiAccessEventEntityDescription] = [
    DOORBELL_EVENT_DESCRIPTION,
    ACCESS_EVENT_DESCRIPTION,
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UnifiAccessConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up UniFi Access event entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        UnifiAccessEventEntity(coordinator, door, description)
        for door in coordinator.data.doors.values()
        for description in EVENT_DESCRIPTIONS
    )


class UnifiAccessEventEntity(UnifiAccessEntity, EventEntity):
    """Representation of a UniFi Access event entity."""

    entity_description: UnifiAccessEventEntityDescription

    def __init__(
        self,
        coordinator: UnifiAccessCoordinator,
        door: Door,
        description: UnifiAccessEventEntityDescription,
    ) -> None:
        """Initialize the event entity."""
        super().__init__(coordinator, door, description.key)
        self.entity_description = description

    async def async_added_to_hass(self) -> None:
        """Subscribe to door events when added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_subscribe_door_events(self._async_handle_event)
        )

    @callback
    def _async_handle_event(self, event: DoorEvent) -> None:
        """Handle incoming event from coordinator."""
        if (
            event.door_id != self._door_id
            or event.category != self.entity_description.category
            or event.event_type not in self.event_types
        ):
            return
        self._trigger_event(event.event_type, event.event_data)
        self.async_write_ha_state()
