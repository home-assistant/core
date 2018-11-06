"""Component for interfacing to Lutron Homeworks keypads.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/homeworks/
"""
import logging
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA)
from homeassistant.components.homeworks import (
    HomeworksDevice, HOMEWORKS_CONTROLLER)
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

DEPENDENCIES = ['homeworks']
REQUIREMENTS = ['pyhomeworks==0.0.1']

_LOGGER = logging.getLogger(__name__)

EVENT_BUTTON_PRESSED = 'button_pressed'
CONF_KEYPADS = 'keypads'
CONF_ADDR = 'addr'
CONF_BUTTONS = 'buttons'

BUTTON_SCHEMA = vol.Schema({cv.positive_int: cv.string})
BUTTONS_SCHEMA = vol.Schema({
    vol.Required(CONF_ADDR): cv.string,
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_BUTTONS): vol.All(cv.ensure_list, [BUTTON_SCHEMA])
})
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_KEYPADS): vol.All(cv.ensure_list, [BUTTONS_SCHEMA])
})


def setup_platform(hass, config, add_entities, discover_info=None):
    """Set up the Homeworks keypads."""
    controller = hass.data[HOMEWORKS_CONTROLLER]
    devs = []
    for keypad in config.get(CONF_KEYPADS):
        name = keypad.get(CONF_NAME)
        addr = keypad.get(CONF_ADDR)
        buttons = keypad.get(CONF_BUTTONS)
        for button in buttons:
            # FIX: This should be done differently
            for num, title in button.items():
                devname = name + '_' + title
                dev = HomeworksKeypad(controller, addr, num, devname)
                devs.append(dev)
    add_entities(devs, True)
    return True


class HomeworksKeypad(HomeworksDevice, BinarySensorDevice):
    """Homeworks Keypad."""

    def __init__(self, controller, addr, num, name):
        """Create keypad with addr, num, and name."""
        HomeworksDevice.__init__(self, controller, addr, name)
        self._num = num
        self._state = None

    @property
    def is_on(self):
        """Return state of the button."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return supported attributes."""
        return {"Homeworks Address": self._addr,
                "Button Number": self._num}

    def callback(self, msg_type, values):
        """Dispatch messages from the controller."""
        from pyhomeworks.pyhomeworks import (
            HW_BUTTON_PRESSED, HW_BUTTON_RELEASED)

        old_state = self._state
        if msg_type == HW_BUTTON_PRESSED and values[1] == self._num:
            self.hass.bus.fire(EVENT_BUTTON_PRESSED,
                               {'entity_id': self.entity_id})
            self._state = True
        elif msg_type == HW_BUTTON_RELEASED and values[1] == self._num:
            self._state = False
        return old_state == self._state
