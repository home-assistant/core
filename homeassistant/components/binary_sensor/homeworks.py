"""Component for interfacing to Lutron Homeworks keypads.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.homeworks/
"""
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect)
from homeassistant.components.binary_sensor import (
    BinarySensorDevice, PLATFORM_SCHEMA)
from homeassistant.components.homeworks import (
    HomeworksDevice, HOMEWORKS_CONTROLLER, ENTITY_SIGNAL)

DEPENDENCIES = ['homeworks']

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
    for keypad in config[CONF_KEYPADS]:
        name = keypad[CONF_NAME]
        addr = keypad[CONF_ADDR]
        buttons = keypad[CONF_BUTTONS]
        for button in buttons:
            for num, title in button.items():
                devname = '{}_{}'.format(name, title)
                dev = HomeworksKeypad(controller, addr, num, devname)
                devs.append(dev)
    add_entities(devs, True)


class HomeworksKeypad(HomeworksDevice, BinarySensorDevice):
    """Homeworks Keypad."""

    def __init__(self, controller, addr, num, name):
        """Create keypad with addr, num, and name."""
        super().__init__(controller, addr, name)
        self._num = num
        self._state = None

    async def async_def_added_to_hass(self):
        """Called when entity is added to hass."""
        signal = ENTITY_SIGNAL.format(self._addr)
        async_dispatcher_connect(
            self.hass, signal, self._update_callback)

    @property
    def is_on(self):
        """Return state of the button."""
        return self._state

    @property
    def device_state_attributes(self):
        """Return state attributes."""
        return {"HomeworksAddress": self._addr,
                "ButtonNumber": self._num}

    @callback
    def _update_callback(self, msg_type, data):
        """Dispatch messages from the controller."""
        from pyhomeworks.pyhomeworks import (
            HW_BUTTON_PRESSED, HW_BUTTON_RELEASED)

        msg_type, values = data
        if msg_type == HW_BUTTON_PRESSED and values[1] == self._num:
            self._state = True
            self.async_schedule_ha_state(True)
        elif msg_type == HW_BUTTON_RELEASED and values[1] == self._num:
            self._state = False
            self.async_schedule_ha_state(True)
