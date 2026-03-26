"""Provides conditions for climates."""

from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.condition import (
    Condition,
    EntityNumericalConditionWithUnitBase,
    make_entity_numerical_condition,
    make_entity_state_condition,
)
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import ATTR_HUMIDITY, ATTR_HVAC_ACTION, DOMAIN, HVACAction, HVACMode


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
