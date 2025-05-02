"""The homee event platform."""

from pyHomee.const import AttributeType
from pyHomee.model import HomeeAttribute

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HomeeConfigEntry
from .entity import HomeeEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomeeConfigEntry,
    async_add_devices: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the homee platform for the event component."""

    devices: list[HomeeEvent] = []
    for node in config_entry.runtime_data.nodes:
        devices.extend(
            HomeeEvent(attribute, config_entry)
            for attribute in node.attributes
            if (attribute.type == AttributeType.UP_DOWN_REMOTE)
        )
    if devices:
        async_add_devices(devices)


class HomeeEvent(HomeeEntity, EventEntity):
    """Representation of a homee event."""

    entity_description = EventEntityDescription(
        key="up_down_remote",
        device_class=EventDeviceClass.BUTTON,
        event_types=["0", "1", "2", "3", "4", "5", "6", "7", "9"],
        translation_key="up_down_remote",
        has_entity_name=True,
    )

    async def async_added_to_hass(self) -> None:
        """Add the homee attribute entity to home assistant."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._attribute.add_on_changed_listener(self._event_triggered)
        )

    @property
    def old_unique_id(self) -> str:
        """Return the old not so unique id of the event entity."""
        return f"{self._attribute.node_id}-event-{self._attribute.id}"

    @callback
    def _event_triggered(self, event: HomeeAttribute) -> None:
        """Handle a homee event."""
        if event.type == AttributeType.UP_DOWN_REMOTE:
            self._trigger_event(str(int(event.current_value)))
            self.schedule_update_ha_state()
