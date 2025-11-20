"""Provides triggers for covers."""

from typing import Final

import voluptuous as vol

from homeassistant.const import CONF_OPTIONS
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import get_device_class
from homeassistant.helpers.trigger import (
    ENTITY_STATE_TRIGGER_SCHEMA_FIRST_LAST,
    EntityTriggerBase,
    Trigger,
    TriggerConfig,
)
from homeassistant.helpers.typing import UNDEFINED, UndefinedType

from . import ATTR_CURRENT_POSITION, CoverDeviceClass, CoverState
from .const import DOMAIN

ATTR_FULLY_CLOSED: Final = "fully_closed"
ATTR_FULLY_OPENED: Final = "fully_opened"

COVER_CLOSED_TRIGGER_SCHEMA = ENTITY_STATE_TRIGGER_SCHEMA_FIRST_LAST.extend(
    {
        vol.Required(CONF_OPTIONS): {
            vol.Required(ATTR_FULLY_CLOSED, default=False): bool,
        },
    }
)

COVER_OPENED_TRIGGER_SCHEMA = ENTITY_STATE_TRIGGER_SCHEMA_FIRST_LAST.extend(
    {
        vol.Required(CONF_OPTIONS): {
            vol.Required(ATTR_FULLY_OPENED, default=False): bool,
        },
    }
)


def get_device_class_or_undefined(
    hass: HomeAssistant, entity_id: str
) -> str | None | UndefinedType:
    """Get the device class of an entity or UNDEFINED if not found."""
    try:
        return get_device_class(hass, entity_id)
    except HomeAssistantError:
        return UNDEFINED


class CoverOpenedClosedTrigger(EntityTriggerBase):
    """Class for cover opened and closed triggers."""

    _attribute: str = ATTR_CURRENT_POSITION
    _attribute_value: int | None = None
    _device_class: CoverDeviceClass | None
    _domain: str = DOMAIN
    _to_states: set[str]

    def is_to_state(self, state: State) -> bool:
        """Check if the state matches the target state."""
        if state.state not in self._to_states:
            return False
        if (
            self._attribute_value is not None
            and (value := state.attributes.get(self._attribute)) is not None
            and value != self._attribute_value
        ):
            return False
        return True

    def entity_filter(self, entities: set[str]) -> set[str]:
        """Filter entities of this domain."""
        entities = super().entity_filter(entities)
        return {
            entity_id
            for entity_id in entities
            if get_device_class_or_undefined(self._hass, entity_id)
            == self._device_class
        }


class CoverClosedTrigger(CoverOpenedClosedTrigger):
    """Class for cover closed triggers."""

    _schema = COVER_CLOSED_TRIGGER_SCHEMA
    _to_states = {CoverState.CLOSED, CoverState.CLOSING}

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the state trigger."""
        super().__init__(hass, config)
        if self._options.get(ATTR_FULLY_CLOSED):
            self._attribute_value = 0


class CoverOpenedTrigger(CoverOpenedClosedTrigger):
    """Class for cover opened triggers."""

    _schema = COVER_OPENED_TRIGGER_SCHEMA
    _to_states = {CoverState.OPEN, CoverState.OPENING}

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the state trigger."""
        super().__init__(hass, config)
        if self._options.get(ATTR_FULLY_OPENED):
            self._attribute_value = 100


def make_cover_closed_trigger(
    device_class: CoverDeviceClass | None,
) -> type[CoverClosedTrigger]:
    """Create an entity state attribute trigger class."""

    class CustomTrigger(CoverClosedTrigger):
        """Trigger for entity state changes."""

        _device_class = device_class

    return CustomTrigger


def make_cover_opened_trigger(
    device_class: CoverDeviceClass | None,
) -> type[CoverOpenedTrigger]:
    """Create an entity state attribute trigger class."""

    class CustomTrigger(CoverOpenedTrigger):
        """Trigger for entity state changes."""

        _device_class = device_class

    return CustomTrigger


TRIGGERS: dict[str, type[Trigger]] = {
    "awning_closed": make_cover_closed_trigger(CoverDeviceClass.AWNING),
    "blind_closed": make_cover_closed_trigger(CoverDeviceClass.BLIND),
    "curtain_closed": make_cover_closed_trigger(CoverDeviceClass.CURTAIN),
    "door_closed": make_cover_closed_trigger(CoverDeviceClass.DOOR),
    "garage_closed": make_cover_closed_trigger(CoverDeviceClass.GARAGE),
    "gate_closed": make_cover_closed_trigger(CoverDeviceClass.GATE),
    "shade_closed": make_cover_closed_trigger(CoverDeviceClass.SHADE),
    "shutter_closed": make_cover_closed_trigger(CoverDeviceClass.SHUTTER),
    "window_closed": make_cover_closed_trigger(CoverDeviceClass.WINDOW),
    "awning_opened": make_cover_opened_trigger(CoverDeviceClass.AWNING),
    "blind_opened": make_cover_opened_trigger(CoverDeviceClass.BLIND),
    "curtain_opened": make_cover_opened_trigger(CoverDeviceClass.CURTAIN),
    "door_opened": make_cover_opened_trigger(CoverDeviceClass.DOOR),
    "garage_opened": make_cover_opened_trigger(CoverDeviceClass.GARAGE),
    "gate_opened": make_cover_opened_trigger(CoverDeviceClass.GATE),
    "shade_opened": make_cover_opened_trigger(CoverDeviceClass.SHADE),
    "shutter_opened": make_cover_opened_trigger(CoverDeviceClass.SHUTTER),
    "window_opened": make_cover_opened_trigger(CoverDeviceClass.WINDOW),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for covers."""
    return TRIGGERS
