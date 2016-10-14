"""
Support for X10 switches.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.x10/
"""
import logging
from subprocess import check_output, CalledProcessError, STDOUT

import voluptuous as vol

from homeassistant.const import (CONF_NAME, CONF_ID, CONF_DEVICES)
from homeassistant.components.switch import (
    SwitchDevice, PLATFORM_SCHEMA)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEVICES): vol.All(cv.ensure_list, [
        {
            vol.Required(CONF_ID): cv.string,
            vol.Required(CONF_NAME): cv.string,
        }
    ]),
})


def x10_command(command):
    """Execute X10 command and check output."""
    return check_output(['heyu'] + command.split(' '), stderr=STDOUT)


def get_status():
    """Get on/off status for all x10 units in default housecode."""
    output = check_output('heyu info | grep monitored', shell=True)
    return output.decode('utf-8').split(' ')[-1].strip('\n()')


def get_unit_status(code):
    """Get on/off status for given unit."""
    unit = int(code[1:])
    return get_status()[16 - int(unit)] == '1'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the x10 Switch platform."""
    try:
        x10_command('info')
    except CalledProcessError as err:
        _LOGGER.error(err.output)
        return False

    add_devices(X10Switch(switch) for switch in config[CONF_DEVICES])


class X10Switch(SwitchDevice):
    """Representation of an X10 Switch."""

    def __init__(self, switch):
        """Initialize an X10 Switch."""
        self._name = switch['name']
        self._id = switch['id']
        self._is_on = False

    @property
    def name(self):
        """Return the display name of this switch."""
        return self._name

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._is_on

    def turn_on(self, **kwargs):
        """Instruct the switch to turn on."""
        x10_command('on ' + self._id)
        self._is_on = True

    def turn_off(self, **kwargs):
        """Instruct the switch to turn off."""
        x10_command('off ' + self._id)
        self._is_on = False

    def update(self):
        """Fetch new state data for this switch."""
        self._is_on = get_unit_status(self._id)
