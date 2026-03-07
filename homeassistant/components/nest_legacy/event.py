"""Event platform for Nest Legacy."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import LOGGER
from .coordinator import NestConfigEntry, NestCoordinator
from .entity import NestEntity
from .events import (
    EVENT_TYPE_CAMERA_FACE,
    EVENT_TYPE_CAMERA_MOTION,
    EVENT_TYPE_CAMERA_PERSON,
    EVENT_TYPE_CAMERA_SOUND,
    EVENT_TYPE_DOORBELL_CHIME,
    NEST_LEGACY_EVENT,
)
from .pynest.models import NestCamera, NestDevice, NestDoorbell

PARALLEL_UPDATES = 0

# Maps Nest API event types to Home Assistant event types
_NEST_EVENT_TYPE_MAP = {
    "motion": EVENT_TYPE_CAMERA_MOTION,
    "person": EVENT_TYPE_CAMERA_PERSON,
    "sound": EVENT_TYPE_CAMERA_SOUND,
    "person-talking": EVENT_TYPE_CAMERA_SOUND,  # Grouped with sound
    "personHeard": EVENT_TYPE_CAMERA_SOUND,
    "dogBarking": EVENT_TYPE_CAMERA_SOUND,
    "face": EVENT_TYPE_CAMERA_FACE,
    "unfamiliar-face": EVENT_TYPE_CAMERA_FACE,
    "doorbell": EVENT_TYPE_DOORBELL_CHIME,
}


# Priority order for selecting a single HA event type when a Nest event carries
# multiple types simultaneously (e.g. ["person", "face"]). More specific types
# rank higher so the richest event type wins.
_NEST_EVENT_TYPE_PRIORITY: list[str] = [
    "doorbell",
    "face",
    "unfamiliar-face",
    "person",
    "personHeard",
    "person-talking",
    "dogBarking",
    "sound",
    "motion",
]


@dataclass(frozen=True, kw_only=True)
class NestEventEntityDescription(EventEntityDescription):
    """Entity description for Nest event entities."""

    event_filter: list[str]
    """A list of Nest API event types that this entity will handle."""
    device_types: tuple[type[NestDevice], ...]
    """The device types this entity is for."""


_DESCRIPTIONS: tuple[NestEventEntityDescription, ...] = (
    NestEventEntityDescription(
        key="chime",
        translation_key="chime",
        device_class=EventDeviceClass.DOORBELL,
        event_types=[EVENT_TYPE_DOORBELL_CHIME],
        event_filter=["doorbell"],
        device_types=(NestDoorbell,),
    ),
    NestEventEntityDescription(
        key="motion",
        translation_key="motion",
        device_class=EventDeviceClass.MOTION,
        event_types=[
            EVENT_TYPE_CAMERA_MOTION,
            EVENT_TYPE_CAMERA_PERSON,
            EVENT_TYPE_CAMERA_SOUND,
            EVENT_TYPE_CAMERA_FACE,
        ],
        event_filter=[
            "motion",
            "person",
            "sound",
            "face",
            "person-talking",
            "personHeard",
            "dogBarking",
            "unfamiliar-face",
        ],
        device_types=(NestCamera,),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NestConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the event platform from a config entry."""
    coordinator = entry.runtime_data
    entities: list[NestEventEntity] = []

    for device in coordinator.data.values():
        for description in _DESCRIPTIONS:
            if not isinstance(device, description.device_types):
                continue
            entities.append(NestEventEntity(coordinator, device, description))

    async_add_entities(entities)


class NestEventEntity(NestEntity[NestDevice], EventEntity):
    """Representation of a Nest event entity."""

    entity_description: NestEventEntityDescription

    def __init__(
        self,
        coordinator: NestCoordinator,
        device: NestDevice,
        description: NestEventEntityDescription,
    ) -> None:
        """Initialize the event entity."""
        super().__init__(coordinator, device)
        self.entity_description = description
        self._attr_unique_id = f"{device.serial_number}-{description.key}"

    @callback
    def _async_handle_event(self, event: Event) -> None:
        """Handle the bus event."""
        event_data = event.data
        if event_data.get("serial_number") != self.device.serial_number:
            return

        nest_event = event_data.get("nest_event", {})
        nest_event_types = nest_event.get("types", [])

        # Find the single most specific matching type via the priority list.
        nest_type = next(
            (
                t
                for t in _NEST_EVENT_TYPE_PRIORITY
                if t in nest_event_types and t in self.entity_description.event_filter
            ),
            None,
        )
        if nest_type is None:
            return

        event_type = _NEST_EVENT_TYPE_MAP.get(nest_type)
        if not event_type:
            LOGGER.warning(
                "Received unmapped Nest event type '%s' for device %s",
                nest_type,
                self.device.serial_number,
            )
            return

        attributes = {
            "nest_event_id": nest_event.get("id"),
            "camera_uuid": nest_event.get("camera_uuid"),
            "start_time": nest_event.get("start_time"),
            "end_time": nest_event.get("end_time"),
            "playback_time": nest_event.get("playback_time"),
            "in_progress": nest_event.get("in_progress"),
            "face_id": nest_event.get("face_id"),
            "face_name": nest_event.get("face_name"),
            "zone_ids": nest_event.get("zone_ids"),
            "importance": nest_event.get("importance"),
            "is_important": nest_event.get("is_important"),
            "face_category": nest_event.get("face_category"),
            "all_event_types": nest_event_types,
        }

        self._trigger_event(event_type, attributes)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.hass.bus.async_listen(NEST_LEGACY_EVENT, self._async_handle_event)
        )
