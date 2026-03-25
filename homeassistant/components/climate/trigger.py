"""Provides triggers for climates."""

import voluptuous as vol

from homeassistant.const import ATTR_TEMPERATURE, CONF_OPTIONS, UnitOfTemperature
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.automation import DomainSpec, NumericalDomainSpec
from homeassistant.helpers.trigger import (
    ENTITY_STATE_TRIGGER_SCHEMA_FIRST_LAST,
    EntityNumericalStateChangedTriggerWithUnitBase,
    EntityNumericalStateCrossedThresholdTriggerWithUnitBase,
    EntityNumericalStateTriggerWithUnitBase,
    EntityTargetStateTriggerBase,
    Trigger,
    TriggerConfig,
    make_entity_numerical_state_changed_trigger,
    make_entity_numerical_state_crossed_threshold_trigger,
    make_entity_target_state_trigger,
    make_entity_transition_trigger,
)
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import ATTR_HUMIDITY, ATTR_HVAC_ACTION, DOMAIN, HVACAction, HVACMode

CONF_HVAC_MODE = "hvac_mode"

HVAC_MODE_CHANGED_TRIGGER_SCHEMA = ENTITY_STATE_TRIGGER_SCHEMA_FIRST_LAST.extend(
    {
        vol.Required(CONF_OPTIONS): {
            vol.Required(CONF_HVAC_MODE): vol.All(
                cv.ensure_list, vol.Length(min=1), [vol.Coerce(HVACMode)]
            ),
        },
    }
)


class HVACModeChangedTrigger(EntityTargetStateTriggerBase):
    """Trigger for entity state changes."""

    _domain_specs = {DOMAIN: DomainSpec()}
    _schema = HVAC_MODE_CHANGED_TRIGGER_SCHEMA

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the state trigger."""
        super().__init__(hass, config)
        self._to_states = set(self._options[CONF_HVAC_MODE])


class _ClimateTargetTemperatureTriggerMixin(EntityNumericalStateTriggerWithUnitBase):
    """Mixin for climate target temperature triggers with unit conversion."""

    _base_unit = UnitOfTemperature.CELSIUS
    _domain_specs = {DOMAIN: NumericalDomainSpec(value_source=ATTR_TEMPERATURE)}
    _unit_converter = TemperatureConverter

    def _get_entity_unit(self, state: State) -> str | None:
        """Get the temperature unit of a climate entity from its state."""
        # Climate entities convert temperatures to the system unit via show_temp
        return self._hass.config.units.temperature_unit


class ClimateTargetTemperatureChangedTrigger(
    _ClimateTargetTemperatureTriggerMixin,
    EntityNumericalStateChangedTriggerWithUnitBase,
):
    """Trigger for climate target temperature value changes."""


class ClimateTargetTemperatureCrossedThresholdTrigger(
    _ClimateTargetTemperatureTriggerMixin,
    EntityNumericalStateCrossedThresholdTriggerWithUnitBase,
):
    """Trigger for climate target temperature value crossing a threshold."""


TRIGGERS: dict[str, type[Trigger]] = {
    "hvac_mode_changed": HVACModeChangedTrigger,
    "started_cooling": make_entity_target_state_trigger(
        {DOMAIN: DomainSpec(value_source=ATTR_HVAC_ACTION)}, HVACAction.COOLING
    ),
    "started_drying": make_entity_target_state_trigger(
        {DOMAIN: DomainSpec(value_source=ATTR_HVAC_ACTION)}, HVACAction.DRYING
    ),
    "target_humidity_changed": make_entity_numerical_state_changed_trigger(
        {DOMAIN: NumericalDomainSpec(value_source=ATTR_HUMIDITY)},
        valid_unit="%",
    ),
    "target_humidity_crossed_threshold": make_entity_numerical_state_crossed_threshold_trigger(
        {DOMAIN: NumericalDomainSpec(value_source=ATTR_HUMIDITY)},
        valid_unit="%",
    ),
    "target_temperature_changed": ClimateTargetTemperatureChangedTrigger,
    "target_temperature_crossed_threshold": ClimateTargetTemperatureCrossedThresholdTrigger,
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
    "started_heating": make_entity_target_state_trigger(
        {DOMAIN: DomainSpec(value_source=ATTR_HVAC_ACTION)}, HVACAction.HEATING
    ),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for climates."""
    return TRIGGERS
