"""Provides conditions for temperature."""

from __future__ import annotations

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE as CLIMATE_ATTR_CURRENT_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.components.water_heater import (
    ATTR_CURRENT_TEMPERATURE as WATER_HEATER_ATTR_CURRENT_TEMPERATURE,
    DOMAIN as WATER_HEATER_DOMAIN,
)
from homeassistant.components.weather import (
    ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_TEMPERATURE_UNIT,
    DOMAIN as WEATHER_DOMAIN,
)
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, UnitOfTemperature
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.automation import NumericalDomainSpec
from homeassistant.helpers.condition import (
    Condition,
    EntityNumericalConditionWithUnitBase,
)
from homeassistant.util.unit_conversion import TemperatureConverter

TEMPERATURE_DOMAIN_SPECS = {
    CLIMATE_DOMAIN: NumericalDomainSpec(
        value_source=CLIMATE_ATTR_CURRENT_TEMPERATURE,
    ),
    SENSOR_DOMAIN: NumericalDomainSpec(
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    WATER_HEATER_DOMAIN: NumericalDomainSpec(
        value_source=WATER_HEATER_ATTR_CURRENT_TEMPERATURE,
    ),
    WEATHER_DOMAIN: NumericalDomainSpec(
        value_source=ATTR_WEATHER_TEMPERATURE,
    ),
}


class TemperatureCondition(EntityNumericalConditionWithUnitBase):
    """Condition for temperature value."""

    _base_unit = UnitOfTemperature.CELSIUS
    _domain_specs = TEMPERATURE_DOMAIN_SPECS
    _unit_converter = TemperatureConverter

    def _get_entity_unit(self, entity_state: State) -> str | None:
        """Get the temperature unit of an entity from its state."""
        if entity_state.domain == SENSOR_DOMAIN:
            return entity_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        if entity_state.domain == WEATHER_DOMAIN:
            return entity_state.attributes.get(ATTR_WEATHER_TEMPERATURE_UNIT)
        # Climate and water_heater: show_temp converts to system unit
        return self._hass.config.units.temperature_unit


CONDITIONS: dict[str, type[Condition]] = {
    "is_value": TemperatureCondition,
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the temperature conditions."""
    return CONDITIONS
