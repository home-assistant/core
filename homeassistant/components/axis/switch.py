"""Support for Axis switches."""

from dataclasses import dataclass
from typing import Any

from axis.models.event import Event, EventTopic

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import AxisConfigEntry
from .entity import AxisEventDescription, AxisEventEntity
from .hub import AxisHub


@dataclass(frozen=True, kw_only=True)
class AxisSwitchDescription(AxisEventDescription, SwitchEntityDescription):
    """Axis switch entity description."""


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
    config_entry: AxisConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Axis switch platform."""
    config_entry.runtime_data.entity_loader.register_platform(
        async_add_entities, AxisSwitch, ENTITY_DESCRIPTIONS
    )


class AxisSwitch(AxisEventEntity, SwitchEntity):
    """Representation of a Axis switch."""

    entity_description: AxisSwitchDescription

    def __init__(
        self, hub: AxisHub, description: AxisSwitchDescription, event: Event
    ) -> None:
        """Initialize the Axis switch."""
        super().__init__(hub, description, event)

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
