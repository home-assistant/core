"""Provides device automations for lights."""
import voluptuous as vol

import homeassistant.components.automation.state as state
from homeassistant.core import split_entity_id
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_TYPE,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_registry import async_entries_for_device
from . import DOMAIN

CONF_TURN_OFF = "turn_off"
CONF_TURN_ON = "turn_on"

ENTITY_TRIGGERS = [
    {
        # Trigger when light is turned on
        CONF_PLATFORM: "device",
        CONF_DOMAIN: DOMAIN,
        CONF_TYPE: CONF_TURN_OFF,
    },
    {
        # Trigger when light is turned off
        CONF_PLATFORM: "device",
        CONF_DOMAIN: DOMAIN,
        CONF_TYPE: CONF_TURN_ON,
    },
]

TRIGGER_SCHEMA = vol.All(
    vol.Schema(
        {
            vol.Required(CONF_PLATFORM): "device",
            vol.Optional(CONF_DEVICE_ID): str,
            vol.Required(CONF_DOMAIN): DOMAIN,
            vol.Required(CONF_ENTITY_ID): cv.entity_id,
            vol.Required(CONF_TYPE): str,
        }
    )
)


def _is_domain(entity, domain):
    return split_entity_id(entity.entity_id)[0] == domain


async def async_attach_trigger(hass, config, action, automation_info):
    """Listen for state changes based on configuration."""
    trigger_type = config.get(CONF_TYPE)
    if trigger_type == CONF_TURN_ON:
        from_state = "off"
        to_state = "on"
    else:
        from_state = "on"
        to_state = "off"
    state_config = {
        state.CONF_ENTITY_ID: config[CONF_ENTITY_ID],
        state.CONF_FROM: from_state,
        state.CONF_TO: to_state,
    }

    return await state.async_trigger(hass, state_config, action, automation_info)


async def async_trigger(hass, config, action, automation_info):
    """Temporary so existing automation framework can be used for testing."""
    return await async_attach_trigger(hass, config, action, automation_info)


async def async_get_triggers(hass, device_id):
    """List device triggers."""
    triggers = []
    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    entities = async_entries_for_device(entity_registry, device_id)
    domain_entities = [x for x in entities if _is_domain(x, DOMAIN)]
    for entity in domain_entities:
        for trigger in ENTITY_TRIGGERS:
            trigger = dict(trigger)
            trigger.update(device_id=device_id, entity_id=entity.entity_id)
            triggers.append(trigger)

    return triggers
