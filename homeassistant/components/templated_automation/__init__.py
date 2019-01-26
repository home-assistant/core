"""
Support for Templated Automation.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/templated_automation/
"""
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.binary_sensor import \
    DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.input_boolean import \
    DOMAIN as INPUT_BOOLEAN_DOMAIN
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.const import CONF_SOURCE, STATE_OFF, \
    SERVICE_TURN_OFF, SERVICE_TURN_ON, ATTR_ENTITY_ID
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change

CONF_BIDIRECTIONAL = 'bidirectional'
CONF_INVERTED = 'inverted'
CONF_TARGET = 'target'

DEFAULT_BIDIRECTIONAL = False
DEFAULT_INVERTED = False

DOMAIN = 'templated_automation'

BINARY_ENTITY_DOMAINS = [
    BINARY_SENSOR_DOMAIN,
    SWITCH_DOMAIN,
    LIGHT_DOMAIN,
    INPUT_BOOLEAN_DOMAIN
]


def binary_entity_id(value: str) -> str:
    """Validate that an Entity ID is from a binary domain."""
    parts = value.split('.', 1)
    if parts[0] not in BINARY_ENTITY_DOMAINS \
            and parts[1] not in BINARY_ENTITY_DOMAINS:
        raise vol.Invalid(
            'Entity ID {} is not from a binary entity domain'.format(value)
        )
    return value


AUTOMATION_TEMPLATE = vol.Schema({
    vol.Required(CONF_SOURCE): vol.All(cv.entity_id, binary_entity_id),
    vol.Required(CONF_TARGET): vol.All(cv.entity_id, binary_entity_id),
    vol.Optional(
        CONF_BIDIRECTIONAL, default=DEFAULT_BIDIRECTIONAL
    ): cv.boolean,
    vol.Optional(CONF_INVERTED, default=DEFAULT_INVERTED): cv.boolean
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(cv.ensure_list, [AUTOMATION_TEMPLATE])
}, extra=vol.ALLOW_EXTRA)

ATTR_NEW_STATE = 'new_state'


async def async_setup(hass, config):
    """Set up the Templated Automation component."""
    automations = {}
    for conf in config[DOMAIN]:
        source = conf[CONF_SOURCE]
        target = conf[CONF_TARGET]
        inverse = conf.get(CONF_INVERTED)
        automation = TemplatedAutomation(hass, source, target, inverse)
        await automation._init()
        automations[source] = automation

    hass.data[DOMAIN] = automations
    return True


class TemplatedAutomation:
    """Represents a Templated Automation."""

    def __init__(self, hass, source, target, inverse):
        """Initialize a Templated Automation object."""
        self._hass = hass
        self._source = source
        self._target = target
        self._inverse = inverse
        self._unsub = None

    async def _init(self):
        """Add the callback for state changes."""
        self._unsub = await async_track_state_change(
            self._hass, self._source, self.handle_state_change
        )

    @callback
    def handle_state_change(self, entity_id, from_s, to_s):
        """Listen for state changes from source and apply to target."""
        service = SERVICE_TURN_OFF if to_s == STATE_OFF \
            and not self._inverse else SERVICE_TURN_ON
        self._hass.async_run_job(
            self._hass.services.async_call(
                'homeassistant', service, {ATTR_ENTITY_ID: self._target}
            )
        )
