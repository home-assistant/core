"""Component to control v6m relays.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/v6m/
"""
import logging
import voluptuous as vol
from homeassistant.components.switch import (
    SwitchDevice, PLATFORM_SCHEMA)
from homeassistant.components.v6m import (
    V6MDevice, DOMAIN)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['v6m']
REQUIREMENTS = ['pyv6m==0.0.1']

CONF_CONTROLLER = 'controller'
CONF_ADDR = 'addr'
CONF_RELAYS = 'relays'


RELAY_SCHEMA = vol.Schema({cv.positive_int: cv.string})
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_CONTROLLER, default=DOMAIN): cv.string,
    vol.Required(CONF_RELAYS): vol.All(cv.ensure_list, [RELAY_SCHEMA])
})


def setup_platform(hass, config, add_entities, discover_info=None):
    """Set up the V6M switches."""
    controller_name = config.get(CONF_CONTROLLER)
    controller = hass.data[controller_name]
    devs = []
    for relay in config.get(CONF_RELAYS):
        # FIX: This should be done differently
        for num, name in relay.items():
            devs.append(V6MRelay(controller, num, name))
    add_entities(devs, True)
    return True


class V6MRelay(V6MDevice, SwitchDevice):
    """V6M Sensor."""

    def __init__(self, controller, num, name):
        """Create switch with num and name."""
        V6MDevice.__init__(self, controller, num, name)
        self._state = None
        controller.register_relay(self)

    @property
    def is_on(self):
        """Return state of the relay."""
        return self._state

    def turn_on(self):
        """Turn relay on."""
        self._controller.set_relay(self.num, True)

    def turn_off(self):
        """Turn relay off."""
        self._controller.set_relay(self.num, False)

    @property
    def device_state_attributes(self):
        """Return supported attributes."""
        return {"Sensor Number": self.num}

    def callback(self, new_state):
        """Process state changes."""
        if self._state != new_state:
            self._state = new_state
            return True
        return False
