"""Provides triggers for water heaters."""

import voluptuous as vol

from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_OPTIONS,
    STATE_OFF,
    UnitOfTemperature,
)
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
    make_entity_origin_state_trigger,
    make_entity_target_state_trigger,
)
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import DOMAIN

CONF_OPERATION_MODE = "operation_mode"

_OPERATION_MODE_CHANGED_TRIGGER_SCHEMA = ENTITY_STATE_TRIGGER_SCHEMA_FIRST_LAST.extend(
    {
        vol.Required(CONF_OPTIONS): {
            vol.Required(CONF_OPERATION_MODE): vol.All(
                cv.ensure_list, vol.Length(min=1), [str]
            ),
        },
    }
)


class WaterHeaterOperationModeChangedTrigger(EntityTargetStateTriggerBase):
    """Trigger for water heater operation mode changes."""

    _domain_specs = {DOMAIN: DomainSpec()}
    _schema = _OPERATION_MODE_CHANGED_TRIGGER_SCHEMA

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the operation mode changed trigger."""
        super().__init__(hass, config)
        self._to_states = set(self._options[CONF_OPERATION_MODE])


class _WaterHeaterTargetTemperatureTriggerMixin(
    EntityNumericalStateTriggerWithUnitBase
):
    """Mixin for water heater target temperature triggers with unit conversion."""

    _base_unit = UnitOfTemperature.CELSIUS
    _domain_specs = {DOMAIN: NumericalDomainSpec(value_source=ATTR_TEMPERATURE)}
    _unit_converter = TemperatureConverter

    def _get_entity_unit(self, state: State) -> str | None:
        """Get the temperature unit of a water heater entity from its state."""
        # Water heater entities convert temperatures to the system unit via show_temp
        return self._hass.config.units.temperature_unit


class WaterHeaterTargetTemperatureChangedTrigger(
    _WaterHeaterTargetTemperatureTriggerMixin,
    EntityNumericalStateChangedTriggerWithUnitBase,
):
    """Trigger for water heater target temperature value changes."""


class WaterHeaterTargetTemperatureCrossedThresholdTrigger(
    _WaterHeaterTargetTemperatureTriggerMixin,
    EntityNumericalStateCrossedThresholdTriggerWithUnitBase,
):
    """Trigger for water heater target temperature value crossing a threshold."""


TRIGGERS: dict[str, type[Trigger]] = {
    "operation_mode_changed": WaterHeaterOperationModeChangedTrigger,
    "target_temperature_changed": WaterHeaterTargetTemperatureChangedTrigger,
    "target_temperature_crossed_threshold": WaterHeaterTargetTemperatureCrossedThresholdTrigger,
    "turned_off": make_entity_target_state_trigger(DOMAIN, STATE_OFF),
    "turned_on": make_entity_origin_state_trigger(DOMAIN, from_state=STATE_OFF),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for water heaters."""
    return TRIGGERS
