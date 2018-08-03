"""
Support for iTach IR Devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/remote.itach/
"""

import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components import remote
from homeassistant.const import (
    DEVICE_DEFAULT_NAME, CONF_NAME, CONF_MAC, CONF_HOST, CONF_PORT,
    CONF_DEVICES)
from homeassistant.components.remote import PLATFORM_SCHEMA

REQUIREMENTS = ['pyitachip2ir==0.0.7']

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 4998
CONNECT_TIMEOUT = 5000

CONF_MODADDR = 'modaddr'
CONF_CONNADDR = 'connaddr'
CONF_COMMANDS = 'commands'
CONF_DATA = 'data'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_MAC): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Required(CONF_DEVICES): vol.All(cv.ensure_list, [{
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_MODADDR): vol.Coerce(int),
        vol.Required(CONF_CONNADDR): vol.Coerce(int),
        vol.Required(CONF_COMMANDS): vol.All(cv.ensure_list, [{
            vol.Required(CONF_NAME): cv.string,
            vol.Required(CONF_DATA): cv.string
        }])
    }])
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the ITach connection and devices."""
    import pyitachip2ir
    itachip2ir = pyitachip2ir.ITachIP2IR(
        config.get(CONF_MAC), config.get(CONF_HOST),
        int(config.get(CONF_PORT)))

    if not itachip2ir.ready(CONNECT_TIMEOUT):
        _LOGGER.error("Unable to find iTach")
        return False

    devices = []
    for data in config.get(CONF_DEVICES):
        name = data.get(CONF_NAME)
        modaddr = int(data.get(CONF_MODADDR, 1))
        connaddr = int(data.get(CONF_CONNADDR, 1))
        cmddatas = ""
        for cmd in data.get(CONF_COMMANDS):
            cmdname = cmd[CONF_NAME].strip()
            if not cmdname:
                cmdname = '""'
            cmddata = cmd[CONF_DATA].strip()
            if not cmddata:
                cmddata = '""'
            cmddatas += "{}\n{}\n".format(cmdname, cmddata)
        itachip2ir.addDevice(name, modaddr, connaddr, cmddatas)
        devices.append(ITachIP2IRRemote(itachip2ir, name))
    add_devices(devices, True)
    return True


class ITachIP2IRRemote(remote.RemoteDevice):
    """Device that sends commands to an ITachIP2IR device."""

    def __init__(self, itachip2ir, name):
        """Initialize device."""
        self.itachip2ir = itachip2ir
        self._power = False
        self._name = name or DEVICE_DEFAULT_NAME

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._power

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._power = True
        self.itachip2ir.send(self._name, "ON", 1)
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        self._power = False
        self.itachip2ir.send(self._name, "OFF", 1)
        self.schedule_update_ha_state()

    def send_command(self, command, **kwargs):
        """Send a command to one device."""
        for single_command in command:
            self.itachip2ir.send(self._name, single_command, 1)

    def update(self):
        """Update the device."""
        self.itachip2ir.update()
