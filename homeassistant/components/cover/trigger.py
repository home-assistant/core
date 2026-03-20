"""Provides triggers for covers."""

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.trigger import EntityTriggerBase, Trigger

from .const import ATTR_IS_CLOSED, DOMAIN, CoverDeviceClass
from .models import CoverDomainSpec


class CoverTriggerBase(EntityTriggerBase[CoverDomainSpec]):
    """Base trigger for cover state changes."""

    def _get_value(self, state: State) -> str | bool | None:
        """Extract the relevant value from state based on domain spec."""
        domain_spec = self._domain_specs[state.domain]
        if domain_spec.value_source is not None:
            return state.attributes.get(domain_spec.value_source)
        return state.state

    def is_valid_state(self, state: State) -> bool:
        """Check if the state matches the target cover state."""
        domain_spec = self._domain_specs[state.domain]
        return self._get_value(state) == domain_spec.target_value

    def is_valid_transition(self, from_state: State, to_state: State) -> bool:
        """Check if the transition is valid for a cover state change."""
        if from_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return False
        if (from_value := self._get_value(from_state)) is None:
            return False
        return from_value != self._get_value(to_state)


def make_cover_opened_trigger(
    *, device_classes: dict[str, str]
) -> type[CoverTriggerBase]:
    """Create a trigger cover_opened."""

    class CoverOpenedTrigger(CoverTriggerBase):
        """Trigger for cover opened state changes."""

        _domain_specs = {
            domain: CoverDomainSpec(
                device_class=dc,
                value_source=ATTR_IS_CLOSED if domain == DOMAIN else None,
                target_value=False if domain == DOMAIN else STATE_ON,
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

        _domain_specs = {
            domain: CoverDomainSpec(
                device_class=dc,
                value_source=ATTR_IS_CLOSED if domain == DOMAIN else None,
                target_value=True if domain == DOMAIN else STATE_OFF,
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
