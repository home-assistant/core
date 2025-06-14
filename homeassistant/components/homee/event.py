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


EVENT_DESCRIPTIONS: dict[AttributeType, EventEntityDescription] = {
    AttributeType.UP_DOWN_REMOTE: EventEntityDescription(
        key="up_down_remote",
        device_class=EventDeviceClass.BUTTON,
        event_types=[
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
        ],
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomeeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add event entities for homee."""

    async_add_entities(
        HomeeEvent(attribute, config_entry, EVENT_DESCRIPTIONS[attribute.type])
        for node in config_entry.runtime_data.nodes
        for attribute in node.attributes
        if attribute.type in EVENT_DESCRIPTIONS and not attribute.editable
    )


class HomeeEvent(HomeeEntity, EventEntity):
    """Representation of a homee event."""

    def __init__(
        self,
        attribute: HomeeAttribute,
        entry: HomeeConfigEntry,
        description: EventEntityDescription,
    ) -> None:
        """Initialize the homee event entity."""
        super().__init__(attribute, entry)
        self.entity_description = description
        self._attr_translation_key = description.key
        if attribute.instance > 0:
            self._attr_translation_key = f"{self._attr_translation_key}_instance"
            self._attr_translation_placeholders = {"instance": str(attribute.instance)}

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
