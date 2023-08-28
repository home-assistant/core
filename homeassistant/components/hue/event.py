"""Hue event entities from Button resources."""
from __future__ import annotations

from typing import Any

from aiohue.v2 import HueBridgeV2
from aiohue.v2.controllers.events import EventType
from aiohue.v2.models.button import Button
from aiohue.v2.models.relative_rotary import RelativeRotary, RelativeRotaryDirection

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .bridge import HueBridge
from .const import DEFAULT_BUTTON_EVENT_TYPES, DEVICE_SPECIFIC_EVENT_TYPES, DOMAIN
from .v2.entity import HueBaseEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up event platform from Hue button resources."""
    bridge: HueBridge = hass.data[DOMAIN][config_entry.entry_id]
    api: HueBridgeV2 = bridge.api

    if bridge.api_version == 1:
        # should not happen, but just in case
        raise NotImplementedError("Event support is only available for V2 bridges")

    # add entities for all button and relative rotary resources
    @callback
    def async_add_entity(
        event_type: EventType,
        resource: Button | RelativeRotary,
    ) -> None:
        """Add entity from Hue resource."""
        if isinstance(resource, RelativeRotary):
            async_add_entities(
                [HueRotaryEventEntity(bridge, api.sensors.relative_rotary, resource)]
            )
        else:
            async_add_entities(
                [HueButtonEventEntity(bridge, api.sensors.button, resource)]
            )

    for controller in (api.sensors.button, api.sensors.relative_rotary):
        # add all current items in controller
        for item in controller:
            async_add_entity(EventType.RESOURCE_ADDED, item)

        # register listener for new items only
        config_entry.async_on_unload(
            controller.subscribe(
                async_add_entity, event_filter=EventType.RESOURCE_ADDED
            )
        )


class HueButtonEventEntity(HueBaseEntity, EventEntity):
    """Representation of a Hue Event entity from a button resource."""

    entity_description = EventEntityDescription(
        key="button",
        device_class=EventDeviceClass.BUTTON,
        translation_key="button",
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the entity."""
        super().__init__(*args, **kwargs)
        # fill the event types based on the features the switch supports
        hue_dev_id = self.controller.get_device(self.resource.id).id
        model_id = self.bridge.api.devices[hue_dev_id].product_data.product_name
        event_types: list[str] = []
        for event_type in DEVICE_SPECIFIC_EVENT_TYPES.get(
            model_id, DEFAULT_BUTTON_EVENT_TYPES
        ):
            event_types.append(event_type.value)
        self._attr_event_types = event_types

    @property
    def name(self) -> str:
        """Return name for the entity."""
        return f"{super().name} {self.resource.metadata.control_id}"

    @callback
    def _handle_event(self, event_type: EventType, resource: Button) -> None:
        """Handle status event for this resource (or it's parent)."""
        if event_type == EventType.RESOURCE_UPDATED and resource.id == self.resource.id:
            self._trigger_event(resource.button.last_event.value)
            self.async_write_ha_state()
            return
        super()._handle_event(event_type, resource)


class HueRotaryEventEntity(HueBaseEntity, EventEntity):
    """Representation of a Hue Event entity from a RelativeRotary resource."""

    entity_description = EventEntityDescription(
        key="rotary",
        device_class=EventDeviceClass.BUTTON,
        translation_key="rotary",
        event_types=[
            RelativeRotaryDirection.CLOCK_WISE.value,
            RelativeRotaryDirection.COUNTER_CLOCK_WISE.value,
        ],
    )

    @callback
    def _handle_event(self, event_type: EventType, resource: RelativeRotary) -> None:
        """Handle status event for this resource (or it's parent)."""
        if event_type == EventType.RESOURCE_UPDATED and resource.id == self.resource.id:
            event_key = resource.relative_rotary.last_event.rotation.direction.value
            event_data = {
                "duration": resource.relative_rotary.last_event.rotation.duration,
                "steps": resource.relative_rotary.last_event.rotation.steps,
                "action": resource.relative_rotary.last_event.action.value,
            }
            self._trigger_event(event_key, event_data)
            self.async_write_ha_state()
            return
        super()._handle_event(event_type, resource)
