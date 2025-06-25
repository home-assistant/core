"""Support for doorbird events."""

from typing import TYPE_CHECKING

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .device import DoorbirdEvent
from .entity import DoorBirdEntity
from .models import DoorBirdConfigEntry, DoorBirdData

EVENT_DESCRIPTIONS = {
    "doorbell": EventEntityDescription(
        key="doorbell",
        translation_key="doorbell",
        device_class=EventDeviceClass.DOORBELL,
        event_types=["ring"],
    ),
    "motion": EventEntityDescription(
        key="motion",
        translation_key="motion",
        device_class=EventDeviceClass.MOTION,
        event_types=["motion"],
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DoorBirdConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the DoorBird event platform."""
    door_bird_data = config_entry.runtime_data
    async_add_entities(
        DoorBirdEventEntity(door_bird_data, doorbird_event, description)
        for doorbird_event in door_bird_data.door_station.event_descriptions
        if (description := EVENT_DESCRIPTIONS.get(doorbird_event.event_type))
    )


class DoorBirdEventEntity(DoorBirdEntity, EventEntity):
    """A doorbird event entity."""

    entity_description: EventEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        door_bird_data: DoorBirdData,
        doorbird_event: DoorbirdEvent,
        entity_description: EventEntityDescription,
    ) -> None:
        """Initialize an event for a doorbird device."""
        super().__init__(door_bird_data)
        self._doorbird_event = doorbird_event
        self.entity_description = entity_description
        event = doorbird_event.event
        self._attr_unique_id = f"{self._mac_addr}_{event}"
        slug_name = event.removeprefix(self._door_station.slug).strip("_")
        friendly_name = slug_name.replace("_", " ")
        self._attr_name = friendly_name[0:1].upper() + friendly_name[1:].lower()

    async def async_added_to_hass(self) -> None:
        """Subscribe to device events."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._doorbird_event.event}",
                self._async_handle_event,
            )
        )

    @callback
    def _async_handle_event(self) -> None:
        """Handle a device event."""
        event_types = self.entity_description.event_types
        if TYPE_CHECKING:
            assert event_types is not None
        self._trigger_event(event_type=event_types[0])
        self.async_write_ha_state()
