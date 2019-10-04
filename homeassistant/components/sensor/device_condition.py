"""Provides device conditions for sensors."""
from typing import List
import voluptuous as vol

from homeassistant.core import HomeAssistant
import homeassistant.components.automation.numeric_state as numeric_state_automation
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ABOVE,
    CONF_BELOW,
    CONF_ENTITY_ID,
    CONF_FOR,
    CONF_TYPE,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
)
from homeassistant.helpers.entity_registry import (
    async_entries_for_device,
    async_get_registry,
)
from homeassistant.helpers import condition, config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import DOMAIN


# mypy: allow-untyped-defs, no-check-untyped-defs

DEVICE_CLASS_NONE = "none"

CONF_IS_BATTERY_LEVEL = "is_battery_level"
CONF_IS_HUMIDITY = "is_humidity"
CONF_IS_ILLUMINANCE = "is_illuminance"
CONF_IS_POWER = "is_power"
CONF_IS_PRESSURE = "is_pressure"
CONF_IS_SIGNAL_STRENGTH = "is_signal_strength"
CONF_IS_TEMPERATURE = "is_temperature"
CONF_IS_TIMESTAMP = "is_timestamp"
CONF_IS_VALUE = "is_value"

ENTITY_CONDITIONS = {
    DEVICE_CLASS_BATTERY: [{CONF_TYPE: CONF_IS_BATTERY_LEVEL}],
    DEVICE_CLASS_HUMIDITY: [{CONF_TYPE: CONF_IS_HUMIDITY}],
    DEVICE_CLASS_ILLUMINANCE: [{CONF_TYPE: CONF_IS_ILLUMINANCE}],
    DEVICE_CLASS_POWER: [{CONF_TYPE: CONF_IS_POWER}],
    DEVICE_CLASS_PRESSURE: [{CONF_TYPE: CONF_IS_PRESSURE}],
    DEVICE_CLASS_SIGNAL_STRENGTH: [{CONF_TYPE: CONF_IS_SIGNAL_STRENGTH}],
    DEVICE_CLASS_TEMPERATURE: [{CONF_TYPE: CONF_IS_TEMPERATURE}],
    DEVICE_CLASS_TIMESTAMP: [{CONF_TYPE: CONF_IS_TIMESTAMP}],
    DEVICE_CLASS_NONE: [{CONF_TYPE: CONF_IS_VALUE}],
}

CONDITION_SCHEMA = vol.All(
    cv.DEVICE_CONDITION_BASE_SCHEMA.extend(
        {
            vol.Required(CONF_ENTITY_ID): cv.entity_id,
            vol.Required(CONF_TYPE): vol.In(
                [
                    CONF_IS_BATTERY_LEVEL,
                    CONF_IS_HUMIDITY,
                    CONF_IS_ILLUMINANCE,
                    CONF_IS_POWER,
                    CONF_IS_PRESSURE,
                    CONF_IS_SIGNAL_STRENGTH,
                    CONF_IS_TEMPERATURE,
                    CONF_IS_TIMESTAMP,
                    CONF_IS_VALUE,
                ]
            ),
            vol.Optional(CONF_BELOW): vol.Any(vol.Coerce(float)),
            vol.Optional(CONF_ABOVE): vol.Any(vol.Coerce(float)),
        }
    ),
    cv.has_at_least_one_key(CONF_BELOW, CONF_ABOVE),
)


async def async_get_conditions(hass: HomeAssistant, device_id: str) -> List[dict]:
    """List device conditions."""
    conditions: List[dict] = []
    entity_registry = await async_get_registry(hass)
    entries = [
        entry
        for entry in async_entries_for_device(entity_registry, device_id)
        if entry.domain == DOMAIN
    ]

    for entry in entries:
        device_class = DEVICE_CLASS_NONE
        state = hass.states.get(entry.entity_id)
        unit_of_measurement = (
            state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) if state else None
        )

        if not state or not unit_of_measurement:
            continue

        if ATTR_DEVICE_CLASS in state.attributes:
            device_class = state.attributes[ATTR_DEVICE_CLASS]

        templates = ENTITY_CONDITIONS.get(
            device_class, ENTITY_CONDITIONS[DEVICE_CLASS_NONE]
        )

        conditions.extend(
            (
                {
                    **template,
                    "condition": "device",
                    "device_id": device_id,
                    "entity_id": entry.entity_id,
                    "domain": DOMAIN,
                }
                for template in templates
            )
        )

    return conditions


def async_condition_from_config(
    config: ConfigType, config_validation: bool
) -> condition.ConditionCheckerType:
    """Evaluate state based on configuration."""
    if config_validation:
        config = CONDITION_SCHEMA(config)
    numeric_state_config = {
        numeric_state_automation.CONF_ENTITY_ID: config[CONF_ENTITY_ID],
        numeric_state_automation.CONF_ABOVE: config.get(CONF_ABOVE),
        numeric_state_automation.CONF_BELOW: config.get(CONF_BELOW),
        numeric_state_automation.CONF_FOR: config.get(CONF_FOR),
    }

    return condition.async_numeric_state_from_config(
        numeric_state_config, config_validation
    )
