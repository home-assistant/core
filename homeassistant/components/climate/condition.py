"""Provides conditions for climates."""

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.const import ATTR_TEMPERATURE, CONF_OPTIONS, UnitOfTemperature
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.condition import (
    ENTITY_STATE_CONDITION_SCHEMA_ANY_ALL,
    Condition,
    ConditionConfig,
    EntityConditionBase,
    EntityNumericalConditionWithUnitBase,
    make_entity_numerical_condition,
    make_entity_state_condition,
)
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import ATTR_HUMIDITY, ATTR_HVAC_ACTION, DOMAIN, HVACAction, HVACMode

CONF_HVAC_MODE = "hvac_mode"

_HVAC_MODE_CONDITION_SCHEMA = ENTITY_STATE_CONDITION_SCHEMA_ANY_ALL.extend(
    {
        vol.Required(CONF_OPTIONS): {
            vol.Required(CONF_HVAC_MODE): vol.All(
                cv.ensure_list, vol.Length(min=1), [vol.Coerce(HVACMode)]
            ),
        },
    }
)


class ClimateHVACModeCondition(EntityConditionBase):
    """Condition for climate HVAC mode."""

    _domain_specs = {DOMAIN: DomainSpec()}
    _schema = _HVAC_MODE_CONDITION_SCHEMA

    def __init__(self, hass: HomeAssistant, config: ConditionConfig) -> None:
        """Initialize the HVAC mode condition."""
        super().__init__(hass, config)
        if TYPE_CHECKING:
            assert config.options is not None
        self._hvac_modes: set[str] = set(config.options[CONF_HVAC_MODE])

    def is_valid_state(self, entity_state: State) -> bool:
        """Check if the state matches any of the expected HVAC modes."""
        return entity_state.state in self._hvac_modes


class ClimateTargetTemperatureCondition(EntityNumericalConditionWithUnitBase):
    """Mixin for climate target temperature conditions with unit conversion."""

    _base_unit = UnitOfTemperature.CELSIUS
    _domain_specs = {DOMAIN: DomainSpec(value_source=ATTR_TEMPERATURE)}
    _unit_converter = TemperatureConverter

    def _get_entity_unit(self, entity_state: State) -> str | None:
        """Get the temperature unit of a climate entity from its state."""
        # Climate entities convert temperatures to the system unit via show_temp
        return self._hass.config.units.temperature_unit


CONDITIONS: dict[str, type[Condition]] = {
    "is_hvac_mode": ClimateHVACModeCondition,
    "is_off": make_entity_state_condition(DOMAIN, HVACMode.OFF),
    "is_on": make_entity_state_condition(
        DOMAIN,
        {
            HVACMode.AUTO,
            HVACMode.COOL,
            HVACMode.DRY,
            HVACMode.FAN_ONLY,
            HVACMode.HEAT,
            HVACMode.HEAT_COOL,
        },
    ),
    "is_cooling": make_entity_state_condition(
        {DOMAIN: DomainSpec(value_source=ATTR_HVAC_ACTION)}, HVACAction.COOLING
    ),
    "is_drying": make_entity_state_condition(
        {DOMAIN: DomainSpec(value_source=ATTR_HVAC_ACTION)}, HVACAction.DRYING
    ),
    "is_heating": make_entity_state_condition(
        {DOMAIN: DomainSpec(value_source=ATTR_HVAC_ACTION)}, HVACAction.HEATING
    ),
    "target_humidity": make_entity_numerical_condition(
        {DOMAIN: DomainSpec(value_source=ATTR_HUMIDITY)},
        valid_unit="%",
    ),
    "target_temperature": ClimateTargetTemperatureCondition,
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the climate conditions."""
    return CONDITIONS
