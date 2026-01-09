"""Provides triggers for alarm control panels."""

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import get_supported_features
from homeassistant.helpers.trigger import (
    EntityTargetStateTriggerBase,
    Trigger,
    make_entity_target_state_trigger,
    make_entity_transition_trigger,
)

from .const import DOMAIN, AlarmControlPanelEntityFeature, AlarmControlPanelState


def supports_feature(hass: HomeAssistant, entity_id: str, features: int) -> bool:
    """Get the device class of an entity or UNDEFINED if not found."""
    try:
        return bool(get_supported_features(hass, entity_id) & features)
    except HomeAssistantError:
        return False


class EntityStateTriggerRequiredFeatures(EntityTargetStateTriggerBase):
    """Trigger for entity state changes."""

    _required_features: int

    def entity_filter(self, entities: set[str]) -> set[str]:
        """Filter entities of this domain."""
        entities = super().entity_filter(entities)
        return {
            entity_id
            for entity_id in entities
            if supports_feature(self._hass, entity_id, self._required_features)
        }


def make_entity_state_trigger_required_features(
    domain: str, to_state: str, required_features: int
) -> type[EntityTargetStateTriggerBase]:
    """Create an entity state trigger class."""

    class CustomTrigger(EntityStateTriggerRequiredFeatures):
        """Trigger for entity state changes."""

        _domain = domain
        _to_states = {to_state}
        _required_features = required_features

    return CustomTrigger


TRIGGERS: dict[str, type[Trigger]] = {
    "armed": make_entity_transition_trigger(
        DOMAIN,
        from_states={
            AlarmControlPanelState.ARMING,
            AlarmControlPanelState.DISARMED,
            AlarmControlPanelState.DISARMING,
            AlarmControlPanelState.PENDING,
            AlarmControlPanelState.TRIGGERED,
        },
        to_states={
            AlarmControlPanelState.ARMED_AWAY,
            AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
            AlarmControlPanelState.ARMED_HOME,
            AlarmControlPanelState.ARMED_NIGHT,
            AlarmControlPanelState.ARMED_VACATION,
        },
    ),
    "armed_away": make_entity_state_trigger_required_features(
        DOMAIN,
        AlarmControlPanelState.ARMED_AWAY,
        AlarmControlPanelEntityFeature.ARM_AWAY,
    ),
    "armed_home": make_entity_state_trigger_required_features(
        DOMAIN,
        AlarmControlPanelState.ARMED_HOME,
        AlarmControlPanelEntityFeature.ARM_HOME,
    ),
    "armed_night": make_entity_state_trigger_required_features(
        DOMAIN,
        AlarmControlPanelState.ARMED_NIGHT,
        AlarmControlPanelEntityFeature.ARM_NIGHT,
    ),
    "armed_vacation": make_entity_state_trigger_required_features(
        DOMAIN,
        AlarmControlPanelState.ARMED_VACATION,
        AlarmControlPanelEntityFeature.ARM_VACATION,
    ),
    "disarmed": make_entity_target_state_trigger(
        DOMAIN, AlarmControlPanelState.DISARMED
    ),
    "triggered": make_entity_target_state_trigger(
        DOMAIN, AlarmControlPanelState.TRIGGERED
    ),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for alarm control panels."""
    return TRIGGERS
