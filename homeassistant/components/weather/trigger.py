"""Provides triggers for weather."""

import probatio

from homeassistant.const import CONF_OPTIONS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.trigger import (
    ENTITY_STATE_TRIGGER_SCHEMA_WITH_BEHAVIOR,
    EntityTargetStateTriggerBase,
    Trigger,
    TriggerConfig,
    make_entity_target_state_trigger,
    make_entity_transition_trigger,
)

from .const import ALL_CONDITIONS, DOMAIN, RAIN_CONDITIONS

CONF_CONDITION = "condition"

NON_RAIN_CONDITIONS = frozenset(ALL_CONDITIONS) - RAIN_CONDITIONS

CONDITION_CHANGED_TRIGGER_SCHEMA = ENTITY_STATE_TRIGGER_SCHEMA_WITH_BEHAVIOR.extend(
    {
        probatio.Required(CONF_OPTIONS): {
            probatio.Required(CONF_CONDITION): probatio.All(
                probatio.EnsureList(),
                probatio.NonEmpty(),
                [probatio.In(ALL_CONDITIONS)],
            ),
        },
    }
)


class ConditionChangedTrigger(EntityTargetStateTriggerBase):
    """Trigger for weather condition changes to one or more specific conditions."""

    _domain_specs = {DOMAIN: DomainSpec()}
    _schema = CONDITION_CHANGED_TRIGGER_SCHEMA

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the trigger."""
        super().__init__(hass, config)
        self._to_states = set(self._options[CONF_CONDITION])


TRIGGERS: dict[str, type[Trigger]] = {
    "condition_changed": ConditionChangedTrigger,
    "started_raining": make_entity_target_state_trigger(DOMAIN, set(RAIN_CONDITIONS)),
    "stopped_raining": make_entity_transition_trigger(
        DOMAIN, from_states=set(RAIN_CONDITIONS), to_states=set(NON_RAIN_CONDITIONS)
    ),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for weather."""
    return TRIGGERS
