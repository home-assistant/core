"""The homee event platform."""

from pyHomee.const import AttributeType
from pyHomee.model import HomeeAttribute

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HomeeConfigEntry
from .entity import HomeeEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomeeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add event entities for homee."""

    async_add_entities(
        HomeeEvent(attribute, config_entry)
        for node in config_entry.runtime_data.nodes
        for attribute in node.attributes
        if attribute.type == AttributeType.UP_DOWN_REMOTE
    )


class HomeeEvent(HomeeEntity, EventEntity):
    """Representation of a homee event."""

    _attr_translation_key = "up_down_remote"
    _attr_event_types = [
        "released",
        "up",
        "down",
        "stop",
        "up_long",
        "down_long",
        "stop_long",
        "c_button",
        "b_button",
        "a_button",
    ]
    _attr_device_class = EventDeviceClass.BUTTON

    async def async_added_to_hass(self) -> None:
        """Add the homee event entity to home assistant."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self._attribute.add_on_changed_listener(self._event_triggered)
        )

    @callback
    def _event_triggered(self, event: HomeeAttribute) -> None:
        """Handle a homee event."""
        if event.type == AttributeType.UP_DOWN_REMOTE:
            self._trigger_event(self.event_types[int(event.current_value)])
            self.schedule_update_ha_state()
