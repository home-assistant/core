"""Provides triggers for doors."""

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.cover import ATTR_IS_CLOSED, DOMAIN as COVER_DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State, split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import get_device_class
from homeassistant.helpers.trigger import EntityTriggerBase, Trigger
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


class DoorTriggerBase(EntityTriggerBase):
    """Base trigger for door state changes."""

    _domains = {BINARY_SENSOR_DOMAIN, COVER_DOMAIN}
    _binary_sensor_target_state: str
    _cover_is_closed_target_value: bool

    def entity_filter(self, entities: set[str]) -> set[str]:
        """Filter entities by door device class."""
        entities = super().entity_filter(entities)
        return {
            entity_id
            for entity_id in entities
            if get_device_class_or_undefined(self._hass, entity_id) == DEVICE_CLASS_DOOR
        }

    def is_valid_state(self, state: State) -> bool:
        """Check if the state matches the target door state."""
        if split_entity_id(state.entity_id)[0] == COVER_DOMAIN:
            return (
                state.attributes.get(ATTR_IS_CLOSED)
                == self._cover_is_closed_target_value
            )
        return state.state == self._binary_sensor_target_state

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check if the transition is valid for a door state change."""
        if from_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return False
        if split_entity_id(from_state.entity_id)[0] == COVER_DOMAIN:
            if (from_is_closed := from_state.attributes.get(ATTR_IS_CLOSED)) is None:
                return False
            return from_is_closed != to_state.attributes.get(ATTR_IS_CLOSED)
        return from_state.state != to_state.state


class DoorOpenedTrigger(DoorTriggerBase):
    """Trigger for door opened state changes."""

    _binary_sensor_target_state = STATE_ON
    _cover_is_closed_target_value = False


class DoorClosedTrigger(DoorTriggerBase):
    """Trigger for door closed state changes."""

    _binary_sensor_target_state = STATE_OFF
    _cover_is_closed_target_value = True


TRIGGERS: dict[str, type[Trigger]] = {
    "opened": DoorOpenedTrigger,
    "closed": DoorClosedTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for doors."""
    return TRIGGERS
