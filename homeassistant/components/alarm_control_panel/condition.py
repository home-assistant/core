"""Provides conditions for alarm control panels."""

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.condition import (
    Condition,
    EntityStateConditionBase,
    make_entity_state_condition,
)
from homeassistant.helpers.entity import get_supported_features

from .const import DOMAIN, AlarmControlPanelEntityFeature, AlarmControlPanelState


def supports_feature(hass: HomeAssistant, entity_id: str, features: int) -> bool:
    """Test if an entity supports the specified features."""
    try:
        return bool(get_supported_features(hass, entity_id) & features)
    except HomeAssistantError:
        return False


class EntityStateRequiredFeaturesCondition(EntityStateConditionBase):
    """State condition."""

    _required_features: int

    def entity_filter(self, entities: set[str]) -> set[str]:
        """Filter entities of this domain with the required features."""
        entities = super().entity_filter(entities)
        return {
            entity_id
            for entity_id in entities
            if supports_feature(self._hass, entity_id, self._required_features)
        }


def make_entity_state_required_features_condition(
    domain: str, to_state: str, required_features: int
) -> type[EntityStateRequiredFeaturesCondition]:
    """Create an entity state condition class with required feature filtering."""

    class CustomCondition(EntityStateRequiredFeaturesCondition):
        """Condition for entity state changes."""

        _domain = domain
        _states = {to_state}
        _required_features = required_features

    return CustomCondition


CONDITIONS: dict[str, type[Condition]] = {
    "is_armed": make_entity_state_condition(
        DOMAIN,
        {
            AlarmControlPanelState.ARMED_AWAY,
            AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
            AlarmControlPanelState.ARMED_HOME,
            AlarmControlPanelState.ARMED_NIGHT,
            AlarmControlPanelState.ARMED_VACATION,
        },
    ),
    "is_armed_away": make_entity_state_required_features_condition(
        DOMAIN,
        AlarmControlPanelState.ARMED_AWAY,
        AlarmControlPanelEntityFeature.ARM_AWAY,
    ),
    "is_armed_home": make_entity_state_required_features_condition(
        DOMAIN,
        AlarmControlPanelState.ARMED_HOME,
        AlarmControlPanelEntityFeature.ARM_HOME,
    ),
    "is_armed_night": make_entity_state_required_features_condition(
        DOMAIN,
        AlarmControlPanelState.ARMED_NIGHT,
        AlarmControlPanelEntityFeature.ARM_NIGHT,
    ),
    "is_armed_vacation": make_entity_state_required_features_condition(
        DOMAIN,
        AlarmControlPanelState.ARMED_VACATION,
        AlarmControlPanelEntityFeature.ARM_VACATION,
    ),
    "is_disarmed": make_entity_state_condition(DOMAIN, AlarmControlPanelState.DISARMED),
    "is_triggered": make_entity_state_condition(
        DOMAIN, AlarmControlPanelState.TRIGGERED
    ),
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the alarm control panel conditions."""
    return CONDITIONS
