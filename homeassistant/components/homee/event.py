"""The homee event platform."""

from pyHomee.const import AttributeType, NodeProfile
from pyHomee.model import HomeeAttribute, HomeeNode

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
    EventEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HomeeConfigEntry
from .entity import HomeeEntity
from .helpers import setup_homee_platform

PARALLEL_UPDATES = 0


REMOTE_PROFILES = [
    NodeProfile.REMOTE,
    NodeProfile.TWO_BUTTON_REMOTE,
    NodeProfile.THREE_BUTTON_REMOTE,
    NodeProfile.FOUR_BUTTON_REMOTE,
]

EVENT_DESCRIPTIONS: dict[AttributeType, EventEntityDescription] = {
    AttributeType.BUTTON_STATE: EventEntityDescription(
        key="button_state",
        device_class=EventDeviceClass.BUTTON,
        event_types=["upper", "lower", "released"],
    ),
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


async def add_event_entities(
    config_entry: HomeeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    nodes: list[HomeeNode],
) -> None:
    """Add homee event entities."""
    async_add_entities(
        HomeeEvent(attribute, config_entry, EVENT_DESCRIPTIONS[attribute.type])
        for node in nodes
        for attribute in node.attributes
        if attribute.type in EVENT_DESCRIPTIONS
        and node.profile in REMOTE_PROFILES
        and not attribute.editable
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HomeeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add event entities for homee."""

    await setup_homee_platform(add_event_entities, async_add_entities, config_entry)


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
        self._trigger_event(self.event_types[int(event.current_value)])
        self.schedule_update_ha_state()
