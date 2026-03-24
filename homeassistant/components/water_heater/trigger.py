"""Provides triggers for water heaters."""

from homeassistant.const import ATTR_TEMPERATURE, STATE_OFF, UnitOfTemperature
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.automation import NumericalDomainSpec
from homeassistant.helpers.trigger import (
    EntityNumericalStateChangedTriggerWithUnitBase,
    EntityNumericalStateCrossedThresholdTriggerWithUnitBase,
    EntityNumericalStateTriggerWithUnitBase,
    Trigger,
    make_entity_origin_state_trigger,
    make_entity_target_state_trigger,
)
from homeassistant.util.unit_conversion import TemperatureConverter

from .const import DOMAIN


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
    "target_temperature_changed": WaterHeaterTargetTemperatureChangedTrigger,
    "target_temperature_crossed_threshold": WaterHeaterTargetTemperatureCrossedThresholdTrigger,
    "turned_off": make_entity_target_state_trigger(DOMAIN, STATE_OFF),
    "turned_on": make_entity_origin_state_trigger(DOMAIN, from_state=STATE_OFF),
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for water heaters."""
    return TRIGGERS
