"""Provides device triggers for sensors."""
import voluptuous as vol

import homeassistant.components.automation.numeric_state as numeric_state_automation
from homeassistant.components.device_automation import TRIGGER_BASE_SCHEMA
from homeassistant.components.device_automation.exceptions import (
    InvalidDeviceAutomationConfig,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_ABOVE,
    CONF_BELOW,
    CONF_ENTITY_ID,
    CONF_FOR,
    CONF_TYPE,
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_CURRENT,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_POWER_FACTOR,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_SIGNAL_STRENGTH,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    DEVICE_CLASS_VOLTAGE,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_registry import async_entries_for_device

from . import DOMAIN

# mypy: allow-untyped-defs, no-check-untyped-defs

DEVICE_CLASS_NONE = "none"

CONF_BATTERY_LEVEL = "battery_level"
CONF_CURRENT = "current"
CONF_ENERGY = "energy"
CONF_HUMIDITY = "humidity"
CONF_ILLUMINANCE = "illuminance"
CONF_POWER = "power"
CONF_POWER_FACTOR = "power_factor"
CONF_PRESSURE = "pressure"
CONF_SIGNAL_STRENGTH = "signal_strength"
CONF_TEMPERATURE = "temperature"
CONF_TIMESTAMP = "timestamp"
CONF_VOLTAGE = "voltage"
CONF_VALUE = "value"

ENTITY_TRIGGERS = {
    DEVICE_CLASS_BATTERY: [{CONF_TYPE: CONF_BATTERY_LEVEL}],
    DEVICE_CLASS_CURRENT: [{CONF_TYPE: CONF_CURRENT}],
    DEVICE_CLASS_ENERGY: [{CONF_TYPE: CONF_ENERGY}],
    DEVICE_CLASS_HUMIDITY: [{CONF_TYPE: CONF_HUMIDITY}],
    DEVICE_CLASS_ILLUMINANCE: [{CONF_TYPE: CONF_ILLUMINANCE}],
    DEVICE_CLASS_POWER: [{CONF_TYPE: CONF_POWER}],
    DEVICE_CLASS_POWER_FACTOR: [{CONF_TYPE: CONF_POWER_FACTOR}],
    DEVICE_CLASS_PRESSURE: [{CONF_TYPE: CONF_PRESSURE}],
    DEVICE_CLASS_SIGNAL_STRENGTH: [{CONF_TYPE: CONF_SIGNAL_STRENGTH}],
    DEVICE_CLASS_TEMPERATURE: [{CONF_TYPE: CONF_TEMPERATURE}],
    DEVICE_CLASS_TIMESTAMP: [{CONF_TYPE: CONF_TIMESTAMP}],
    DEVICE_CLASS_VOLTAGE: [{CONF_TYPE: CONF_VOLTAGE}],
    DEVICE_CLASS_NONE: [{CONF_TYPE: CONF_VALUE}],
}


TRIGGER_SCHEMA = vol.All(
    TRIGGER_BASE_SCHEMA.extend(
        {
            vol.Required(CONF_ENTITY_ID): cv.entity_id,
            vol.Required(CONF_TYPE): vol.In(
                [
                    CONF_BATTERY_LEVEL,
                    CONF_CURRENT,
                    CONF_ENERGY,
                    CONF_HUMIDITY,
                    CONF_ILLUMINANCE,
                    CONF_POWER,
                    CONF_POWER_FACTOR,
                    CONF_PRESSURE,
                    CONF_SIGNAL_STRENGTH,
                    CONF_TEMPERATURE,
                    CONF_TIMESTAMP,
                    CONF_VOLTAGE,
                    CONF_VALUE,
                ]
            ),
            vol.Optional(CONF_BELOW): vol.Any(vol.Coerce(float)),
            vol.Optional(CONF_ABOVE): vol.Any(vol.Coerce(float)),
            vol.Optional(CONF_FOR): cv.positive_time_period_dict,
        }
    ),
    cv.has_at_least_one_key(CONF_BELOW, CONF_ABOVE),
)


async def async_attach_trigger(hass, config, action, automation_info):
    """Listen for state changes based on configuration."""
    numeric_state_config = {
        numeric_state_automation.CONF_PLATFORM: "numeric_state",
        numeric_state_automation.CONF_ENTITY_ID: config[CONF_ENTITY_ID],
    }
    if CONF_ABOVE in config:
        numeric_state_config[numeric_state_automation.CONF_ABOVE] = config[CONF_ABOVE]
    if CONF_BELOW in config:
        numeric_state_config[numeric_state_automation.CONF_BELOW] = config[CONF_BELOW]
    if CONF_FOR in config:
        numeric_state_config[CONF_FOR] = config[CONF_FOR]

    numeric_state_config = numeric_state_automation.TRIGGER_SCHEMA(numeric_state_config)
    return await numeric_state_automation.async_attach_trigger(
        hass, numeric_state_config, action, automation_info, platform_type="device"
    )


async def async_get_triggers(hass, device_id):
    """List device triggers."""
    triggers = []
    entity_registry = await hass.helpers.entity_registry.async_get_registry()

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

        templates = ENTITY_TRIGGERS.get(
            device_class, ENTITY_TRIGGERS[DEVICE_CLASS_NONE]
        )

        triggers.extend(
            {
                **automation,
                "platform": "device",
                "device_id": device_id,
                "entity_id": entry.entity_id,
                "domain": DOMAIN,
            }
            for automation in templates
        )

    return triggers


async def async_get_trigger_capabilities(hass, config):
    """List trigger capabilities."""
    state = hass.states.get(config[CONF_ENTITY_ID])
    unit_of_measurement = (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) if state else None
    )

    if not state or not unit_of_measurement:
        raise InvalidDeviceAutomationConfig

    return {
        "extra_fields": vol.Schema(
            {
                vol.Optional(
                    CONF_ABOVE, description={"suffix": unit_of_measurement}
                ): vol.Coerce(float),
                vol.Optional(
                    CONF_BELOW, description={"suffix": unit_of_measurement}
                ): vol.Coerce(float),
                vol.Optional(CONF_FOR): cv.positive_time_period_dict,
            }
        )
    }
