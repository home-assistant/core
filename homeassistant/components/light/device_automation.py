"""Provides device automations for lights."""
import voluptuous as vol

import homeassistant.components.automation.state as state
from homeassistant.core import split_entity_id
from homeassistant.const import CONF_DOMAIN, CONF_ENTITY_ID, CONF_TYPE
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_registry import async_entries_for_device
from . import DOMAIN

ENTITY_TRIGGERS = [
    {
        # Trigger when light is turned on
        CONF_DOMAIN: DOMAIN,
        CONF_TYPE: 'turn_on',
    },
    {
        # Trigger when light is turned off
        CONF_DOMAIN: DOMAIN,
        CONF_TYPE: 'turn_off',
    },
]

TRIGGER_SCHEMA = vol.All(vol.Schema({
    vol.Required(CONF_DOMAIN): DOMAIN,
    vol.Required(CONF_ENTITY_ID): cv.entity_ids,
    vol.Required(CONF_TYPE): str,
}))


def _is_domain(entity, domain):
    return split_entity_id(entity.entity_id)[0] == domain


async def async_attach_trigger(hass, config, action, automation_info):
    """Listen for state changes based on configuration."""
    trigger_type = config.get(CONF_TYPE)
    if trigger_type == 'turn_on':
        to_state = 'on'
    else:
        to_state = 'off'
    state_config = {
        state.CONF_ENTITY_ID: config[CONF_ENTITY_ID],
        state.CONF_TO: to_state
    }

    return await state.async_trigger(hass, state_config, action,
                                     automation_info)


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
            trigger.update(entity_id=entity.entity_id)
            triggers.append(trigger)

    return triggers
