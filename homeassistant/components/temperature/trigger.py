"""Provides triggers for temperature."""

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
from homeassistant.helpers.trigger import (
    EntityNumericalStateChangedTriggerWithUnitBase,
    EntityNumericalStateCrossedThresholdTriggerWithUnitBase,
    EntityNumericalStateTriggerWithUnitBase,
    Trigger,
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
        value_source=WaterHeaterStateAttribute.CURRENT_TEMPERATURE
    ),
    WEATHER_DOMAIN: DomainSpec(
        value_source=WeatherEntityStateAttribute.TEMPERATURE,
    ),
}


class _TemperatureTriggerMixin(EntityNumericalStateTriggerWithUnitBase):
    """Mixin for temperature triggers with filtering and conversion."""

    _base_unit = UnitOfTemperature.CELSIUS
    _domain_specs = TEMPERATURE_DOMAIN_SPECS
    _unit_converter = TemperatureConverter

    @override
    def _should_include(self, state: State) -> bool:
        """Skip attribute-source entities that lack the temperature attribute.

        For domains whose tracked value comes from an attribute
        (climate / water_heater / weather), require the attribute to be
        present; otherwise the all/count check would treat an entity that
        cannot report a temperature as a non-match and block behavior=last.
        Sensor entities source their value from `state.state`, so they
        fall through to the base impl.
        """
        if not super()._should_include(state):
            return False
        domain_spec = self._domain_specs[state.domain]
        if domain_spec.value_source is None:
            return True
        return state.attributes.get(domain_spec.value_source) is not None

    @override
    def _get_entity_unit(self, state: State) -> str | None:
        """Get the temperature unit of an entity from its state."""
        if state.domain == SENSOR_DOMAIN:
            return state.attributes.get(EntityStateAttribute.UNIT_OF_MEASUREMENT)
        if state.domain == WEATHER_DOMAIN:
            return state.attributes.get(WeatherEntityStateAttribute.TEMPERATURE_UNIT)
        # Climate and water_heater: show_temp converts to system unit
        return self._hass.config.units.temperature_unit


class TemperatureChangedTrigger(
    _TemperatureTriggerMixin, EntityNumericalStateChangedTriggerWithUnitBase
):
    """Trigger for temperature value changes across multiple domains."""


class TemperatureCrossedThresholdTrigger(
    _TemperatureTriggerMixin, EntityNumericalStateCrossedThresholdTriggerWithUnitBase
):
    """Trigger for temperature value crossing a threshold across multiple domains."""


TRIGGERS: dict[str, type[Trigger]] = {
    "changed": TemperatureChangedTrigger,
    "crossed_threshold": TemperatureCrossedThresholdTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for temperature."""
    return TRIGGERS
