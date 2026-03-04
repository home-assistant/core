"""Provides triggers for doors."""

from homeassistant.components.cover import CoverState
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import get_device_class
from homeassistant.helpers.trigger import EntityTargetStateTriggerBase, Trigger
from homeassistant.helpers.typing import UNDEFINED, UndefinedType

DEVICE_CLASS_DOOR = "door"


def get_device_class_or_undefined(
    hass: HomeAssistant, entity_id: str
) -> str | None | UndefinedType:
    """Get the device class of an entity or UNDEFINED if not found."""
    try:
        return get_device_class(hass, entity_id)
    except HomeAssistantError:
        return UNDEFINED


class DoorOpenedTrigger(EntityTargetStateTriggerBase):
    """Trigger for door opened state changes."""

    _domains = {"binary_sensor", "cover"}
    _to_states = {STATE_ON, CoverState.OPEN, CoverState.OPENING}

    def entity_filter(self, entities: set[str]) -> set[str]:
        """Filter entities by door device class."""
        entities = super().entity_filter(entities)
        return {
            entity_id
            for entity_id in entities
            if get_device_class_or_undefined(self._hass, entity_id) == DEVICE_CLASS_DOOR
        }


TRIGGERS: dict[str, type[Trigger]] = {
    "opened": DoorOpenedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for doors."""
    return TRIGGERS
