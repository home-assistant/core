"""Provides triggers for temperature."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

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
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ABOVE,
    CONF_BELOW,
    CONF_OPTIONS,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, State, split_entity_id
from homeassistant.helpers.trigger import (
    ATTR_BEHAVIOR,
    BEHAVIOR_ANY,
    BEHAVIOR_FIRST,
    BEHAVIOR_LAST,
    CONF_LOWER_LIMIT,
    CONF_THRESHOLD_TYPE,
    CONF_UPPER_LIMIT,
    ENTITY_STATE_TRIGGER_SCHEMA,
    EntityNumericalStateAttributeChangedTriggerBase,
    EntityNumericalStateAttributeCrossedThresholdTriggerBase,
    EntityNumericalStateBase,
    ThresholdType,
    Trigger,
    TriggerConfig,
    _number_or_entity,
    _validate_limits_for_threshold_type,
    _validate_range,
    get_device_class_or_undefined,
)
from homeassistant.util.unit_conversion import TemperatureConverter

CONF_UNIT = "unit"

_UNIT_MAP = {
    "celsius": UnitOfTemperature.CELSIUS,
    "fahrenheit": UnitOfTemperature.FAHRENHEIT,
}


def _validate_temperature_unit(value: str) -> str:
    """Convert temperature unit option to UnitOfTemperature."""
    if value in _UNIT_MAP:
        return _UNIT_MAP[value]
    raise vol.Invalid(f"Unknown temperature unit: {value}")


_UNIT_VALIDATOR = _validate_temperature_unit

TEMPERATURE_CHANGED_TRIGGER_SCHEMA = ENTITY_STATE_TRIGGER_SCHEMA.extend(
    {
        vol.Required(CONF_OPTIONS): vol.All(
            {
                vol.Optional(CONF_ABOVE): _number_or_entity,
                vol.Optional(CONF_BELOW): _number_or_entity,
                vol.Optional(CONF_UNIT): _UNIT_VALIDATOR,
            },
            _validate_range(CONF_ABOVE, CONF_BELOW),
        )
    }
)

TEMPERATURE_CROSSED_THRESHOLD_TRIGGER_SCHEMA = ENTITY_STATE_TRIGGER_SCHEMA.extend(
    {
        vol.Required(CONF_OPTIONS): vol.All(
            {
                vol.Required(ATTR_BEHAVIOR, default=BEHAVIOR_ANY): vol.In(
                    [BEHAVIOR_FIRST, BEHAVIOR_LAST, BEHAVIOR_ANY]
                ),
                vol.Optional(CONF_LOWER_LIMIT): _number_or_entity,
                vol.Optional(CONF_UPPER_LIMIT): _number_or_entity,
                vol.Required(CONF_THRESHOLD_TYPE): vol.Coerce(ThresholdType),
                vol.Optional(CONF_UNIT): _UNIT_VALIDATOR,
            },
            _validate_range(CONF_LOWER_LIMIT, CONF_UPPER_LIMIT),
            _validate_limits_for_threshold_type,
        )
    }
)

_DOMAINS = {SENSOR_DOMAIN, CLIMATE_DOMAIN, WATER_HEATER_DOMAIN, WEATHER_DOMAIN}


class _TemperatureTriggerMixin(EntityNumericalStateBase):
    """Mixin for temperature triggers providing entity filtering, value extraction, and unit conversion."""

    _attributes = {
        CLIMATE_DOMAIN: CLIMATE_ATTR_CURRENT_TEMPERATURE,
        SENSOR_DOMAIN: None,  # Use state.state
        WATER_HEATER_DOMAIN: WATER_HEATER_ATTR_CURRENT_TEMPERATURE,
        WEATHER_DOMAIN: ATTR_WEATHER_TEMPERATURE,
    }
    _domains = _DOMAINS

    def __init__(self, hass: HomeAssistant, config: TriggerConfig) -> None:
        """Initialize the trigger."""
        super().__init__(hass, config)
        self._trigger_unit: str = self._options.get(
            CONF_UNIT, hass.config.units.temperature_unit
        )

    def entity_filter(self, entities: set[str]) -> set[str]:
        """Filter entities: sensor only with device_class temperature."""
        entities = super().entity_filter(entities)
        return {
            entity_id
            for entity_id in entities
            if split_entity_id(entity_id)[0] != SENSOR_DOMAIN
            or get_device_class_or_undefined(self._hass, entity_id)
            == SensorDeviceClass.TEMPERATURE
        }

    def _get_entity_unit(self, state: State) -> str | None:
        """Get the temperature unit of an entity from its state."""
        domain = split_entity_id(state.entity_id)[0]
        if domain == SENSOR_DOMAIN:
            return state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        if domain == WEATHER_DOMAIN:
            return state.attributes.get(
                ATTR_WEATHER_TEMPERATURE_UNIT,
                self._hass.config.units.temperature_unit,
            )
        # Climate and water_heater: show_temp converts to system unit
        return self._hass.config.units.temperature_unit

    def _get_tracked_value(self, state: State) -> Any:
        """Get the temperature value converted to the trigger's configured unit."""
        raw_value = super()._get_tracked_value(state)
        if raw_value is None:
            return None

        entity_unit = self._get_entity_unit(state)
        if entity_unit is None or entity_unit == self._trigger_unit:
            return raw_value

        try:
            return TemperatureConverter.convert(
                float(raw_value), entity_unit, self._trigger_unit
            )
        except TypeError, ValueError:
            return raw_value  # Let the base class converter handle the error


class TemperatureChangedTrigger(
    _TemperatureTriggerMixin, EntityNumericalStateAttributeChangedTriggerBase
):
    """Trigger for temperature value changes across multiple domains."""

    _schema = TEMPERATURE_CHANGED_TRIGGER_SCHEMA


class TemperatureCrossedThresholdTrigger(
    _TemperatureTriggerMixin, EntityNumericalStateAttributeCrossedThresholdTriggerBase
):
    """Trigger for temperature value crossing a threshold across multiple domains."""

    _schema = TEMPERATURE_CROSSED_THRESHOLD_TRIGGER_SCHEMA


TRIGGERS: dict[str, type[Trigger]] = {
    "changed": TemperatureChangedTrigger,
    "crossed_threshold": TemperatureCrossedThresholdTrigger,
}


async def async_get_triggers(hass: HomeAssistant) -> dict[str, type[Trigger]]:
    """Return the triggers for temperature."""
    return TRIGGERS
