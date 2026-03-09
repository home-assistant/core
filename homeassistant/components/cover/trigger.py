"""Provides triggers for covers."""

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State, split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import get_device_class
from homeassistant.helpers.trigger import EntityTriggerBase
from homeassistant.helpers.typing import UNDEFINED, UndefinedType

from . import ATTR_IS_CLOSED, DOMAIN


def get_device_class_or_undefined(
    hass: HomeAssistant, entity_id: str
) -> str | None | UndefinedType:
    """Get the device class of an entity or UNDEFINED if not found."""
    try:
        return get_device_class(hass, entity_id)
    except HomeAssistantError:
        return UNDEFINED


class CoverTriggerBase(EntityTriggerBase):
    """Base trigger for cover state changes."""

    _domains = {BINARY_SENSOR_DOMAIN, DOMAIN}
    _binary_sensor_target_state: str
    _cover_is_closed_target_value: bool
    _device_classes: dict[str, str]

    def entity_filter(self, entities: set[str]) -> set[str]:
        """Filter entities by cover device class."""
        entities = super().entity_filter(entities)
        return {
            entity_id
            for entity_id in entities
            if get_device_class_or_undefined(self._hass, entity_id)
            == self._device_classes[split_entity_id(entity_id)[0]]
        }

    def is_valid_state(self, state: State) -> bool:
        """Check if the state matches the target cover state."""
        if split_entity_id(state.entity_id)[0] == DOMAIN:
            return (
                state.attributes.get(ATTR_IS_CLOSED)
                == self._cover_is_closed_target_value
            )
        return state.state == self._binary_sensor_target_state

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check if the transition is valid for a cover state change."""
        if from_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return False
        if split_entity_id(from_state.entity_id)[0] == DOMAIN:
            if (from_is_closed := from_state.attributes.get(ATTR_IS_CLOSED)) is None:
                return False
            return from_is_closed != to_state.attributes.get(ATTR_IS_CLOSED)  # type: ignore[no-any-return]
        return from_state.state != to_state.state


class CoverOpenedTriggerBase(CoverTriggerBase):
    """Base trigger for cover opened state changes."""

    _binary_sensor_target_state = STATE_ON
    _cover_is_closed_target_value = False


class CoverClosedTriggerBase(CoverTriggerBase):
    """Base trigger for cover closed state changes."""

    _binary_sensor_target_state = STATE_OFF
    _cover_is_closed_target_value = True
