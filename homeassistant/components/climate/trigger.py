"""Provides triggers for climates."""

import voluptuous as vol

from homeassistant.const import ATTR_TEMPERATURE, CONF_OPTIONS
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.trigger import (
    ENTITY_STATE_TRIGGER_SCHEMA_FIRST_LAST,
    EntityTargetStateTriggerBase,
    Trigger,
    TriggerConfig,
    make_entity_numerical_state_attribute_changed_trigger,
    make_entity_numerical_state_attribute_crossed_threshold_trigger,
    make_entity_target_state_attribute_trigger,
    make_entity_target_state_trigger,
    make_entity_transition_trigger,
)

from .const import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HUMIDITY,
    ATTR_HVAC_ACTION,
    DOMAIN,
    HVACAction,
    HVACMode,
)

CONF_HVAC_MODE = "hvac_mode"

HVAC_MODE_CHANGED_TRIGGER_SCHEMA = ENTITY_STATE_TRIGGER_SCHEMA_FIRST_LAST.extend(
    {
        vol.Required(CONF_OPTIONS): {
            vol.Required(CONF_HVAC_MODE): vol.All(
                cv.ensure_list, vol.Length(min=1), [HVACMode]
            ),
        },
    }
)


class HVACModeChangedTrigger(EntityTargetStateTriggerBase):
    """Trigger for entity state changes."""

    _domain = DOMAIN
    _schema = HVAC_MODE_CHANGED_TRIGGER_SCHEMA

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the state trigger."""
        super().__init__(hass, config)
        self._to_states = set(self._options[CONF_HVAC_MODE])


TRIGGERS: dict[str, type[Trigger]] = {
    "current_humidity_changed": make_entity_numerical_state_attribute_changed_trigger(
        DOMAIN, ATTR_CURRENT_HUMIDITY
    ),
    "current_humidity_crossed_threshold": make_entity_numerical_state_attribute_crossed_threshold_trigger(
        DOMAIN, ATTR_CURRENT_HUMIDITY
    ),
    "current_temperature_changed": make_entity_numerical_state_attribute_changed_trigger(
        DOMAIN, ATTR_CURRENT_TEMPERATURE
    ),
    "current_temperature_crossed_threshold": make_entity_numerical_state_attribute_crossed_threshold_trigger(
        DOMAIN, ATTR_CURRENT_TEMPERATURE
    ),
    "hvac_mode_changed": HVACModeChangedTrigger,
    "started_cooling": make_entity_target_state_attribute_trigger(
        DOMAIN, ATTR_HVAC_ACTION, HVACAction.COOLING
    ),
    "started_drying": make_entity_target_state_attribute_trigger(
        DOMAIN, ATTR_HVAC_ACTION, HVACAction.DRYING
    ),
    "target_humidity_changed": make_entity_numerical_state_attribute_changed_trigger(
        DOMAIN, ATTR_HUMIDITY
    ),
    "target_humidity_crossed_threshold": make_entity_numerical_state_attribute_crossed_threshold_trigger(
        DOMAIN, ATTR_HUMIDITY
    ),
    "target_temperature_changed": make_entity_numerical_state_attribute_changed_trigger(
        DOMAIN, ATTR_TEMPERATURE
    ),
    "target_temperature_crossed_threshold": make_entity_numerical_state_attribute_crossed_threshold_trigger(
        DOMAIN, ATTR_TEMPERATURE
    ),
    "turned_off": make_entity_target_state_trigger(DOMAIN, HVACMode.OFF),
    "turned_on": make_entity_transition_trigger(
        DOMAIN,
        from_states={
            HVACMode.OFF,
        },
        to_states={
            HVACMode.AUTO,
            HVACMode.COOL,
            HVACMode.DRY,
            HVACMode.FAN_ONLY,
            HVACMode.HEAT,
            HVACMode.HEAT_COOL,
        },
    ),
    "started_heating": make_entity_target_state_attribute_trigger(
        DOMAIN, ATTR_HVAC_ACTION, HVACAction.HEATING
    ),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for climates."""
    return TRIGGERS
