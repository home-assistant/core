"""Support for SimpliSafe events."""

from simplipy.websocket import WebsocketEvent

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import WEBSOCKET_EVENTS_TO_FIRE_HASS_EVENT, SimpliSafe, SimpliSafeConfigEntry
from .entity import SimpliSafeEntity
from .typing import SystemType


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SimpliSafeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SimpliSafe events based on a config entry."""
    simplisafe = entry.runtime_data
    async_add_entities(
        SimpliSafeEvent(simplisafe, system) for system in simplisafe.systems.values()
    )


class SimpliSafeEvent(SimpliSafeEntity, EventEntity):
    """Define a SimpliSafe event entity."""

    _attr_event_types = WEBSOCKET_EVENTS_TO_FIRE_HASS_EVENT
    _attr_translation_key = "system_events"

    def __init__(self, simplisafe: SimpliSafe, system: SystemType) -> None:
        """Initialize."""
        super().__init__(
            simplisafe,
            system,
            additional_websocket_events=WEBSOCKET_EVENTS_TO_FIRE_HASS_EVENT,
        )
        self._attr_unique_id = f"{self._system.serial}-event"

    @callback
    def async_update_from_websocket_event(self, event: WebsocketEvent) -> None:
        """Update the entity when new data comes from the websocket."""
        assert event.event_type is not None
        self._trigger_event(
            event.event_type,
            event_attributes={
                "changed_by": event.changed_by,
                "info": event.info,
                "sensor_name": event.sensor_name,
                "sensor_serial": event.sensor_serial,
                "sensor_type": event.sensor_type.name if event.sensor_type else None,
            },
        )
