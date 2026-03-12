"""Provides triggers for covers."""

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.trigger import EntityTriggerBase, Trigger, ValueSource

from .const import ATTR_IS_CLOSED, DOMAIN, CoverDeviceClass


class CoverTriggerBase(EntityTriggerBase):
    """Base trigger for cover state changes."""

    _binary_sensor_target_state: str
    _cover_is_closed_target_value: bool

    def is_valid_state(self, state: State) -> bool:
        """Check if the state matches the target cover state."""
        vs = self.get_value_source_for_entity(state.entity_id)
        if vs is not None and vs.value_source is not None:
            return (
                state.attributes.get(vs.value_source)
                == self._cover_is_closed_target_value
            )
        return state.state == self._binary_sensor_target_state

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check if the transition is valid for a cover state change."""
        if from_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return False
        vs = self.get_value_source_for_entity(from_state.entity_id)
        if vs is not None and vs.value_source is not None:
            if (from_is_closed := from_state.attributes.get(vs.value_source)) is None:
                return False
            return from_is_closed != to_state.attributes.get(vs.value_source)  # type: ignore[no-any-return]
        return from_state.state != to_state.state


def make_cover_opened_trigger(
    *, device_classes: dict[str, str]
) -> type[CoverTriggerBase]:
    """Create a trigger cover_opened."""

    class CoverOpenedTrigger(CoverTriggerBase):
        """Trigger for cover opened state changes."""

        _binary_sensor_target_state = STATE_ON
        _cover_is_closed_target_value = False
        _value_sources = {
            domain: ValueSource(
                device_class=dc,
                value_source=ATTR_IS_CLOSED if domain == DOMAIN else None,
            )
            for domain, dc in device_classes.items()
        }

    return CoverOpenedTrigger


def make_cover_closed_trigger(
    *, device_classes: dict[str, str]
) -> type[CoverTriggerBase]:
    """Create a trigger cover_closed."""

    class CoverClosedTrigger(CoverTriggerBase):
        """Trigger for cover closed state changes."""

        _binary_sensor_target_state = STATE_OFF
        _cover_is_closed_target_value = True
        _value_sources = {
            domain: ValueSource(
                device_class=dc,
                value_source=ATTR_IS_CLOSED if domain == DOMAIN else None,
            )
            for domain, dc in device_classes.items()
        }

    return CoverClosedTrigger


# Concrete triggers for cover device classes (cover-only, no binary sensor)

DEVICE_CLASSES_AWNING: dict[str, str] = {DOMAIN: CoverDeviceClass.AWNING}
DEVICE_CLASSES_BLIND: dict[str, str] = {DOMAIN: CoverDeviceClass.BLIND}
DEVICE_CLASSES_CURTAIN: dict[str, str] = {DOMAIN: CoverDeviceClass.CURTAIN}
DEVICE_CLASSES_SHADE: dict[str, str] = {DOMAIN: CoverDeviceClass.SHADE}
DEVICE_CLASSES_SHUTTER: dict[str, str] = {DOMAIN: CoverDeviceClass.SHUTTER}

TRIGGERS: dict[str, type[Trigger]] = {
    "awning_opened": make_cover_opened_trigger(device_classes=DEVICE_CLASSES_AWNING),
    "awning_closed": make_cover_closed_trigger(device_classes=DEVICE_CLASSES_AWNING),
    "blind_opened": make_cover_opened_trigger(device_classes=DEVICE_CLASSES_BLIND),
    "blind_closed": make_cover_closed_trigger(device_classes=DEVICE_CLASSES_BLIND),
    "curtain_opened": make_cover_opened_trigger(device_classes=DEVICE_CLASSES_CURTAIN),
    "curtain_closed": make_cover_closed_trigger(device_classes=DEVICE_CLASSES_CURTAIN),
    "shade_opened": make_cover_opened_trigger(device_classes=DEVICE_CLASSES_SHADE),
    "shade_closed": make_cover_closed_trigger(device_classes=DEVICE_CLASSES_SHADE),
    "shutter_opened": make_cover_opened_trigger(device_classes=DEVICE_CLASSES_SHUTTER),
    "shutter_closed": make_cover_closed_trigger(device_classes=DEVICE_CLASSES_SHUTTER),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for covers."""
    return TRIGGERS
