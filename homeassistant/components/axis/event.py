"""Support for Axis event entities."""

from __future__ import annotations

from dataclasses import dataclass

from axis.models.event import Event, EventTopic

from homeassistant.components.event import (
    DoorbellEventType,
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AxisConfigEntry
from .entity import AxisEventDescription, AxisEventEntity

DOORBELL_CONFIG = ("I8116-E", "0")


@dataclass(frozen=True, kw_only=True)
class AxisEventPlatformDescription(AxisEventDescription, EventEntityDescription):
    """Axis event entity description."""


ENTITY_DESCRIPTIONS = (
    AxisEventPlatformDescription(
        key="Doorbell",
        device_class=EventDeviceClass.DOORBELL,
        event_types=[DoorbellEventType.RING],
        event_topic=EventTopic.PORT_INPUT,
        name_fn=lambda _hub, _event: "Doorbell",
        supported_fn=lambda hub, event: (hub.config.model, event.id) == DOORBELL_CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AxisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up an Axis event platform."""
    config_entry.runtime_data.entity_loader.register_platform(
        async_add_entities, AxisEvent, ENTITY_DESCRIPTIONS
    )


class AxisEvent(AxisEventEntity, EventEntity):
    """Representation of an Axis event entity."""

    entity_description: AxisEventPlatformDescription

    @callback
    def async_event_callback(self, event: Event) -> None:
        """Handle Axis event updates."""
        if event.is_tripped:
            self._trigger_event(DoorbellEventType.RING)
            self.async_write_ha_state()
