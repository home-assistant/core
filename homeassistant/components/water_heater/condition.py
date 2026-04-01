"""Provides conditions for water heaters."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_OPTIONS,
    STATE_OFF,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.condition import (
    ENTITY_STATE_CONDITION_SCHEMA_ANY_ALL,
    Condition,
    ConditionConfig,
    EntityConditionBase,
    EntityNumericalConditionWithUnitBase,
    make_entity_state_condition,
)
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import DOMAIN

ATTR_OPERATION_MODE = "operation_mode"


_OPERATION_MODE_CONDITION_SCHEMA = ENTITY_STATE_CONDITION_SCHEMA_ANY_ALL.extend(
    {
        vol.Required(CONF_OPTIONS): {
            vol.Required(ATTR_OPERATION_MODE): vol.All(
                cv.ensure_list, vol.Length(min=1), [str]
            ),
        },
    }
)


class WaterHeaterOnCondition(EntityConditionBase):
    """Condition for water heater being on."""

    _domain_specs = {DOMAIN: DomainSpec()}

    def is_valid_state(self, entity_state: State) -> bool:
        """Check if the water heater is in a non-off state."""
        return entity_state.state != STATE_OFF


class WaterHeaterOperationModeCondition(EntityConditionBase):
    """Condition for water heater operation mode."""

    _domain_specs = {DOMAIN: DomainSpec()}
    _schema = _OPERATION_MODE_CONDITION_SCHEMA

    def __init__(self, hass: HomeAssistant, config: ConditionConfig) -> None:
        """Initialize the operation mode condition."""
        super().__init__(hass, config)
        if TYPE_CHECKING:
            assert config.options is not None
        self._operation_modes: set[str] = set(config.options[ATTR_OPERATION_MODE])

    def is_valid_state(self, entity_state: State) -> bool:
        """Check if the state matches any of the expected operation modes."""
        return entity_state.state in self._operation_modes


class WaterHeaterTargetTemperatureCondition(EntityNumericalConditionWithUnitBase):
    """Condition for water heater target temperature."""

    _base_unit = UnitOfTemperature.CELSIUS
    _domain_specs = {DOMAIN: DomainSpec(value_source=ATTR_TEMPERATURE)}
    _unit_converter = TemperatureConverter

    def _get_entity_unit(self, entity_state: State) -> str | None:
        """Get the temperature unit of a water heater entity from its state."""
        # Water heater entities convert temperatures to the system unit via show_temp
        return self._hass.config.units.temperature_unit


CONDITIONS: dict[str, type[Condition]] = {
    "is_off": make_entity_state_condition(DOMAIN, STATE_OFF),
    "is_on": WaterHeaterOnCondition,
    "is_operation_mode": WaterHeaterOperationModeCondition,
    "is_target_temperature": WaterHeaterTargetTemperatureCondition,
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the water heater conditions."""
    return CONDITIONS
