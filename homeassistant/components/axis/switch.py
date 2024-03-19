"""Support for Axis switches."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import partial
from typing import Any

from axis.models.event import Event, EventOperation, EventTopic

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import AxisEventEntity
from .hub import AxisHub


@dataclass(frozen=True, kw_only=True)
class AxisSwitchDescription(SwitchEntityDescription):
    """Axis switch entity description."""

    event_topic: EventTopic
    """Event topic that provides state updates."""
    name_fn: Callable[[AxisHub, Event], str]
    """Function providing the corresponding name to the event ID."""
    supported_fn: Callable[[AxisHub, Event], bool]
    """Function validating if event is supported."""


ENTITY_DESCRIPTIONS = (
    AxisSwitchDescription(
        key="Relay state control",
        device_class=SwitchDeviceClass.OUTLET,
        entity_category=EntityCategory.CONFIG,
        event_topic=EventTopic.RELAY,
        supported_fn=lambda hub, event: isinstance(int(event.id), int),
        name_fn=lambda hub, event: hub.api.vapix.ports[event.id].name,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Axis switch platform."""
    hub = AxisHub.get_hub(hass, config_entry)

    @callback
    def register_platform(descriptions: Iterable[AxisSwitchDescription]) -> None:
        """Register entity platform to create entities on event initialized signal."""

        @callback
        def create_entity(description: AxisSwitchDescription, event: Event) -> None:
            """Create Axis entity."""
            if description.supported_fn(hub, event):
                async_add_entities([AxisSwitch(hub, description, event)])

        for description in descriptions:
            hub.api.event.subscribe(
                partial(create_entity, description),
                topic_filter=description.event_topic,
                operation_filter=EventOperation.INITIALIZED,
            )

    register_platform(ENTITY_DESCRIPTIONS)


class AxisSwitch(AxisEventEntity, SwitchEntity):
    """Representation of a Axis switch."""

    def __init__(
        self, hub: AxisHub, description: AxisSwitchDescription, event: Event
    ) -> None:
        """Initialize the Axis switch."""
        super().__init__(event, hub)
        self.entity_description = description
        self._attr_name = description.name_fn(hub, event) or self._attr_name
        self._attr_is_on = event.is_tripped

    @callback
    def async_event_callback(self, event: Event) -> None:
        """Update light state."""
        self._attr_is_on = event.is_tripped
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on switch."""
        await self.hub.api.vapix.ports.close(self._event_id)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off switch."""
        await self.hub.api.vapix.ports.open(self._event_id)
