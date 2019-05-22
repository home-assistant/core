"""Provides device automations for lights."""
import voluptuous as vol

import homeassistant.components.automation.state as state
from homeassistant.const import CONF_ENTITY_ID, CONF_PLATFORM, CONF_TYPE
import homeassistant.helpers.config_validation as cv
from . import DOMAIN

ENTITY_TRIGGERS = [
    {
        # Trigger when light is turned on
        CONF_PLATFORM: '.{}.device_automation'.format(DOMAIN),
        CONF_TYPE: 'turn_on',
    },
    {
        # Trigger when light is turned off
        CONF_PLATFORM: '.{}.device_automation'.format(DOMAIN),
        CONF_TYPE: 'turn_off',
    },
]

TRIGGER_SCHEMA = vol.All(vol.Schema({
    vol.Required(CONF_PLATFORM): '.{}.device_automation'.format(DOMAIN),
    vol.Required(CONF_ENTITY_ID): cv.entity_ids,
    vol.Required(CONF_TYPE): str,
}))


async def async_trigger(hass, config, action, automation_info):
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
