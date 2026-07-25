"""Provides conditions for temperature."""

from typing import override

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    ClimateEntityStateAttribute,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN, SensorDeviceClass
from homeassistant.components.water_heater import (
    DOMAIN as WATER_HEATER_DOMAIN,
    WaterHeaterStateAttribute,
)
from homeassistant.components.weather import (
    DOMAIN as WEATHER_DOMAIN,
    WeatherEntityStateAttribute,
)
from homeassistant.const import EntityStateAttribute, UnitOfTemperature
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.condition import (
    Condition,
    EntityNumericalConditionWithUnitBase,
)
from homeassistant.util.unit_conversion import TemperatureConverter

TEMPERATURE_DOMAIN_SPECS: dict[str, DomainSpec] = {
    CLIMATE_DOMAIN: DomainSpec(
        value_source=ClimateEntityStateAttribute.CURRENT_TEMPERATURE,
    ),
    SENSOR_DOMAIN: DomainSpec(
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    WATER_HEATER_DOMAIN: DomainSpec(
        value_source=WaterHeaterStateAttribute.CURRENT_TEMPERATURE,
    ),
    WEATHER_DOMAIN: DomainSpec(
        value_source=WeatherEntityStateAttribute.TEMPERATURE,
    ),
}


class TemperatureCondition(EntityNumericalConditionWithUnitBase):
    """Condition for temperature value."""

    _base_unit = UnitOfTemperature.CELSIUS
    _domain_specs = TEMPERATURE_DOMAIN_SPECS
    _unit_converter = TemperatureConverter

    @override
    def _should_include(self, state: State) -> bool:
        """Skip attribute-source entities that lack the temperature attribute.

        Mirrors the temperature trigger: for climate / water_heater /
        weather (attribute-based), the entity is filtered when the source
        attribute is absent; sensor entities (state-value-based) fall
        through to the base impl.
        """
        if not super()._should_include(state):
            return False
        domain_spec = self._domain_specs[state.domain]
        if domain_spec.value_source is None:
            return True
        return state.attributes.get(domain_spec.value_source) is not None

    @override
    def _get_entity_unit(self, entity_state: State) -> str | None:
        """Get the temperature unit of an entity from its state."""
        if entity_state.domain == SENSOR_DOMAIN:
            return entity_state.attributes.get(EntityStateAttribute.UNIT_OF_MEASUREMENT)
        if entity_state.domain == WEATHER_DOMAIN:
            return entity_state.attributes.get(
                WeatherEntityStateAttribute.TEMPERATURE_UNIT
            )
        # Climate and water_heater: show_temp converts to system unit
        return self._hass.config.units.temperature_unit


CONDITIONS: dict[str, type[Condition]] = {
    "is_value": TemperatureCondition,
}


async def async_get_conditions(hass: HomeAssistant) -> dict[str, type[Condition]]:
    """Return the temperature conditions."""
    return CONDITIONS
