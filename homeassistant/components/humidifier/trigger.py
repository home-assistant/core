"""Provides triggers for humidifiers."""

import voluptuous as vol

from homeassistant.const import ATTR_MODE, CONF_OPTIONS, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.entity import get_supported_features
from homeassistant.helpers.trigger import (
    ENTITY_STATE_TRIGGER_SCHEMA_FIRST_LAST,
    EntityTargetStateTriggerBase,
    Trigger,
    TriggerConfig,
    make_entity_target_state_trigger,
)

from .const import ATTR_ACTION, DOMAIN, HumidifierAction, HumidifierEntityFeature

CONF_MODE = "mode"

MODE_CHANGED_TRIGGER_SCHEMA = ENTITY_STATE_TRIGGER_SCHEMA_FIRST_LAST.extend(
    {
        vol.Required(CONF_OPTIONS): {
            vol.Required(CONF_MODE): vol.All(cv.ensure_list, vol.Length(min=1), [str]),
        },
    }
)


def _supports_feature(hass: HomeAssistant, entity_id: str, features: int) -> bool:
    """Test if an entity supports the specified features."""
    try:
        return bool(get_supported_features(hass, entity_id) & features)
    except HomeAssistantError:
        return False


class ModeChangedTrigger(EntityTargetStateTriggerBase):
    """Trigger for humidifier mode changes."""

    _domain_specs = {DOMAIN: DomainSpec(value_source=ATTR_MODE)}
    _schema = MODE_CHANGED_TRIGGER_SCHEMA

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the mode trigger."""
        super().__init__(hass, config)
        self._to_states = set(self._options[CONF_MODE])

    def entity_filter(self, entities: set[str]) -> set[str]:
        """Filter entities of this domain."""
        entities = super().entity_filter(entities)
        return {
            entity_id
            for entity_id in entities
            if _supports_feature(self._hass, entity_id, HumidifierEntityFeature.MODES)
        }


TRIGGERS: dict[str, type[Trigger]] = {
    "mode_changed": ModeChangedTrigger,
    "started_drying": make_entity_target_state_trigger(
        {DOMAIN: DomainSpec(value_source=ATTR_ACTION)}, HumidifierAction.DRYING
    ),
    "started_humidifying": make_entity_target_state_trigger(
        {DOMAIN: DomainSpec(value_source=ATTR_ACTION)}, HumidifierAction.HUMIDIFYING
    ),
    "turned_off": make_entity_target_state_trigger(DOMAIN, STATE_OFF),
    "turned_on": make_entity_target_state_trigger(DOMAIN, STATE_ON),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for humidifiers."""
    return TRIGGERS
