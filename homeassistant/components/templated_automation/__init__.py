"""
Support for Templated Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/templated_automation
"""
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_SOURCE, EVENT_STATE_CHANGED, STATE_OFF, \
    SERVICE_TURN_OFF, SERVICE_TURN_ON, ATTR_ENTITY_ID, ATTR_STATE

CONF_BIDIRECTIONAL = 'bidirectional'
CONF_INVERSE = 'inverse'
CONF_TARGET = 'target'

DEFAULT_BIDIRECTIONAL = False
DEFAULT_INVERSE = False

DOMAIN = 'templated_automation'

AUTOMATION_TEMPLATE = vol.Schema({
    vol.Required(CONF_SOURCE): cv.entity_id,
    vol.Required(CONF_TARGET): cv.entity_id,
    vol.Optional(
        CONF_BIDIRECTIONAL, default=DEFAULT_BIDIRECTIONAL
    ): cv.boolean,
    vol.Optional(CONF_INVERSE, default=DEFAULT_INVERSE): cv.boolean
})

CONFIG_SCHEMA = vol.Schema({
    vol.Optional(DOMAIN): vol.All(cv.ensure_list, [AUTOMATION_TEMPLATE])
}, extra=vol.ALLOW_EXTRA)

ATTR_NEW_STATE = 'new_state'


async def async_setup(hass, config):
    """Set up the Templated Automation component."""
    automations = {}
    for conf in config[DOMAIN]:
        source = conf[CONF_SOURCE]
        target = conf[CONF_TARGET]
        inverse = conf.get(CONF_INVERSE)
        automations[source] = TemplatedAutomation(source, target, inverse)
        if conf.get(CONF_BIDIRECTIONAL):
            automations[target] = TemplatedAutomation(target, source, inverse)

    hass.data[DOMAIN] = automations

    async def handle_event(event):
        entity_id = event.data[ATTR_ENTITY_ID]
        if entity_id not in hass.data[DOMAIN]:
            return

        automation = hass.data[DOMAIN][entity_id]
        new_state = getattr(event.data.get(ATTR_NEW_STATE), ATTR_STATE, None)

        if not new_state:
            return

        service = SERVICE_TURN_OFF if new_state == STATE_OFF \
            and not automation.inverse else SERVICE_TURN_ON

        await hass.services.async_call(
            'homeassistant', service, {ATTR_ENTITY_ID: automation.target}
        )

    hass.bus.async_listen(EVENT_STATE_CHANGED, handle_event)

    return True


class TemplatedAutomation:
    """Represents a Templated Automation."""

    def __init__(self, source, target, inverse):
        """Initialize a Templated Automation object."""
        self.source = source
        self.target = target
        self.inverse = inverse
