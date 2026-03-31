"""Provides triggers for temperature."""

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
from homeassistant.helpers.automation import DomainSpec
from homeassistant.helpers.trigger import (
    EntityNumericalStateChangedTriggerWithUnitBase,
    EntityNumericalStateCrossedThresholdTriggerWithUnitBase,
    EntityNumericalStateTriggerWithUnitBase,
    Trigger,
)
from homeassistant.util.unit_conversion import TemperatureConverter

TEMPERATURE_DOMAIN_SPECS = {
    CLIMATE_DOMAIN: DomainSpec(
        value_source=CLIMATE_ATTR_CURRENT_TEMPERATURE,
    ),
    SENSOR_DOMAIN: DomainSpec(
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    WATER_HEATER_DOMAIN: DomainSpec(value_source=WATER_HEATER_ATTR_CURRENT_TEMPERATURE),
    WEATHER_DOMAIN: DomainSpec(
        value_source=ATTR_WEATHER_TEMPERATURE,
    ),
}


class _TemperatureTriggerMixin(EntityNumericalStateTriggerWithUnitBase):
    """Mixin for temperature triggers providing entity filtering, value extraction, and unit conversion."""

    _base_unit = UnitOfTemperature.CELSIUS
    _domain_specs = TEMPERATURE_DOMAIN_SPECS
    _unit_converter = TemperatureConverter

    def _get_entity_unit(self, state: State) -> str | None:
        """Get the temperature unit of an entity from its state."""
        if state.domain == SENSOR_DOMAIN:
            return state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        if state.domain == WEATHER_DOMAIN:
            return state.attributes.get(ATTR_WEATHER_TEMPERATURE_UNIT)
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
