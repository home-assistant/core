"""Events on Zigbee Home Automation networks."""

from __future__ import annotations

import functools
from typing import Any, cast

from zha.application.platforms.event import BaseEvent, EntityStateChangedEvent
from zha.const import STATE_CHANGED

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import ZHAEntity
from .helpers import (
    SIGNAL_ADD_ENTITIES,
    EntityData,
    async_add_entities as zha_async_add_entities,
    get_zha_data,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Zigbee Home Automation sensor from config entry."""
    zha_data = get_zha_data(hass)
    entities_to_create = zha_data.platforms[Platform.EVENT]

    unsub = async_dispatcher_connect(
        hass,
        SIGNAL_ADD_ENTITIES,
        functools.partial(
            zha_async_add_entities, async_add_entities, Event, entities_to_create
        ),
    )
    config_entry.async_on_unload(unsub)


# pylint: disable-next=hass-invalid-inheritance # needs fixing
class Event(ZHAEntity, EventEntity):
    """ZHA sensor."""

    def __init__(self, entity_data: EntityData, **kwargs: Any) -> None:
        """Initialize the ZHA select entity."""
        super().__init__(entity_data, **kwargs)
        entity = cast(BaseEvent, self.entity_data.entity)

        if entity.device_class is not None:
            self._attr_device_class = EventDeviceClass(entity.device_class)

        self._attr_event_types = entity.event_types

    @callback
    def _handle_entity_events(self, event: Any) -> None:
        """Entity state changed."""

        self.debug("Handling event from entity: %s", event)
        if isinstance(event, EntityStateChangedEvent) and event.event == STATE_CHANGED:
            state = self.entity_data.entity.state
            if event_type := state.get("event_type"):
                self._trigger_event(event_type, state.get("event_attributes"))
                self.async_write_ha_state()
