"""Provides device automations for lights."""
import logging
import voluptuous as vol

import homeassistant.components.automation.numeric_state as numeric_state
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    CONF_ABOVE,
    CONF_BELOW,
    CONF_CONDITION,
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_FOR,
    CONF_PLATFORM,
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
from homeassistant.core import split_entity_id
from homeassistant.helpers.entity_registry import async_entries_for_device
from homeassistant.helpers import condition, config_validation as cv

from . import DOMAIN


_LOGGER = logging.getLogger(__name__)
# mypy: allow-untyped-defs, no-check-untyped-defs

DEVICE_CLASS_NONE = "none"

CONF_IS_BATTERY_LEVEL = "is_battery_level"
CONF_IS_HUMIDITY = "is_humidity"
CONF_IS_ILLUMINANCE = "is_illuminance"
CONF_IS_POWER = "is_power"
CONF_IS_PRESSURE = "is_pressure"
CONF_IS_SIGNAL_STRENGTH = "is_signal_strength"
CONF_IS_TEMPERATURE = "is_temperature"
CONF_IS_TIMESTAMP = "is_timestapm"
CONF_IS_VALUE = "is_value"

CONF_BATTERY_LEVEL = "battery_level"
CONF_HUMIDITY = "humidity"
CONF_ILLUMINANCE = "illuminance"
CONF_POWER = "power"
CONF_PRESSURE = "pressure"
CONF_SIGNAL_STRENGTH = "signal_strength"
CONF_TEMPERATURE = "temperature"
CONF_TIMESTAMP = "timestapm"
CONF_VALUE = "value"

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

ENTITY_TRIGGERS = {
    DEVICE_CLASS_BATTERY: [{CONF_TYPE: CONF_BATTERY_LEVEL}],
    DEVICE_CLASS_HUMIDITY: [{CONF_TYPE: CONF_HUMIDITY}],
    DEVICE_CLASS_ILLUMINANCE: [{CONF_TYPE: CONF_ILLUMINANCE}],
    DEVICE_CLASS_POWER: [{CONF_TYPE: CONF_POWER}],
    DEVICE_CLASS_PRESSURE: [{CONF_TYPE: CONF_PRESSURE}],
    DEVICE_CLASS_SIGNAL_STRENGTH: [{CONF_TYPE: CONF_SIGNAL_STRENGTH}],
    DEVICE_CLASS_TEMPERATURE: [{CONF_TYPE: CONF_TEMPERATURE}],
    DEVICE_CLASS_TIMESTAMP: [{CONF_TYPE: CONF_TIMESTAMP}],
    DEVICE_CLASS_NONE: [{CONF_TYPE: CONF_VALUE}],
}

CONDITION_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(CONF_CONDITION): "device",
            vol.Required(CONF_DEVICE_ID): str,
            vol.Required(CONF_DOMAIN): DOMAIN,
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
                ]
            ),
            vol.Optional(CONF_BELOW): vol.Any(None, vol.Coerce(float)),
            vol.Optional(CONF_ABOVE): vol.Any(None, vol.Coerce(float)),
            vol.Optional(CONF_FOR): vol.Any(
                vol.All(cv.time_period, cv.positive_timedelta),
                cv.template,
                cv.template_complex,
            ),
        }
    ),
    cv.has_at_least_one_non_empty_key(CONF_BELOW, CONF_ABOVE),
)

TRIGGER_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(CONF_PLATFORM): "device",
            vol.Required(CONF_DEVICE_ID): str,
            vol.Required(CONF_DOMAIN): DOMAIN,
            vol.Required(CONF_ENTITY_ID): cv.entity_id,
            vol.Required(CONF_TYPE): vol.In(
                [
                    CONF_BATTERY_LEVEL,
                    CONF_HUMIDITY,
                    CONF_ILLUMINANCE,
                    CONF_POWER,
                    CONF_PRESSURE,
                    CONF_SIGNAL_STRENGTH,
                    CONF_TEMPERATURE,
                    CONF_TIMESTAMP,
                ]
            ),
            vol.Optional(CONF_BELOW): vol.Any(None, vol.Coerce(float)),
            vol.Optional(CONF_ABOVE): vol.Any(None, vol.Coerce(float)),
            vol.Optional(CONF_FOR): vol.Any(
                vol.All(cv.time_period, cv.positive_timedelta),
                cv.template,
                cv.template_complex,
            ),
        }
    ),
    cv.has_at_least_one_non_empty_key(CONF_BELOW, CONF_ABOVE),
)


def async_condition_from_config(config, config_validation):
    """Evaluate state based on configuration."""
    config = CONDITION_SCHEMA(config)
    numeric_state_config = {
        numeric_state.CONF_ENTITY_ID: config[CONF_ENTITY_ID],
        numeric_state.CONF_ABOVE: config.get(CONF_ABOVE),
        numeric_state.CONF_BELOW: config.get(CONF_BELOW),
        numeric_state.CONF_FOR: config.get(CONF_FOR),
    }

    return condition.async_numeric_state_from_config(
        numeric_state_config, config_validation
    )


async def async_trigger(hass, config, action, automation_info):
    """Listen for state changes based on configuration."""
    config = TRIGGER_SCHEMA(config)
    numeric_state_config = {
        numeric_state.CONF_ENTITY_ID: config[CONF_ENTITY_ID],
        numeric_state.CONF_ABOVE: config.get(CONF_ABOVE),
        numeric_state.CONF_BELOW: config.get(CONF_BELOW),
        numeric_state.CONF_FOR: config.get(CONF_FOR),
    }

    return await numeric_state.async_trigger(
        hass, numeric_state_config, action, automation_info
    )


def _is_domain(entity, domain):
    return split_entity_id(entity.entity_id)[0] == domain


async def _async_get_automations(hass, device_id, automation_templates, domain):
    """List device automations."""
    automations = []
    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    entities = async_entries_for_device(entity_registry, device_id)
    domain_entities = [x for x in entities if _is_domain(x, domain)]
    for entity in domain_entities:
        device_class = DEVICE_CLASS_NONE
        entity_id = entity.entity_id
        entity = hass.states.get(entity_id)
        if entity and ATTR_DEVICE_CLASS in entity.attributes:
            device_class = entity.attributes[ATTR_DEVICE_CLASS]
        automation_template = automation_templates[device_class]

        for automation in automation_template:
            automation = dict(automation)
            automation.update(device_id=device_id, entity_id=entity_id, domain=domain)
            automations.append(automation)

    return automations


async def async_get_conditions(hass, device_id):
    """List device conditions."""
    automations = await _async_get_automations(
        hass, device_id, ENTITY_CONDITIONS, DOMAIN
    )
    for automation in automations:
        automation.update(condition="device", above=None, below=None)
    return automations


async def async_get_triggers(hass, device_id):
    """List device triggers."""
    automations = await _async_get_automations(hass, device_id, ENTITY_TRIGGERS, DOMAIN)
    for automation in automations:
        automation.update(platform="device", above=None, below=None)
    return automations
