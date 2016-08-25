"""
Support for wake on lan.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.wake_on_lan/
"""
import logging
import platform
import subprocess as sp

import voluptuous as vol

from homeassistant.components.switch import (SwitchDevice, PLATFORM_SCHEMA)
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (CONF_HOST, CONF_NAME)

REQUIREMENTS = ['wakeonlan==0.2.2']

_LOGGER = logging.getLogger(__name__)

CONF_MAC_ADDRESS = 'mac_address'

DEFAULT_NAME = 'Wake on LAN'
DEFAULT_PING_TIMEOUT = 1

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MAC_ADDRESS): cv.string,
    vol.Optional(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Add wake on lan switch."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    mac_address = config.get(CONF_MAC_ADDRESS)

    add_devices_callback([WOLSwitch(hass, name, host, mac_address)])


class WOLSwitch(SwitchDevice):
    """Representation of a wake on lan switch."""

    def __init__(self, hass, name, host, mac_address):
        """Initialize the WOL switch."""
        from wakeonlan import wol
        self._hass = hass
        self._name = name
        self._host = host
        self._mac_address = mac_address
        self._state = False
        self._wol = wol
        self.update()

    @property
    def should_poll(self):
        """Poll for status regularly."""
        return True

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._state

    @property
    def name(self):
        """The name of the switch."""
        return self._name

    def turn_on(self):
        """Turn the device on."""
        self._wol.send_magic_packet(self._mac_address)
        self.update_ha_state()

    def turn_off(self):
        """Do nothing."""
        pass

    def update(self):
        """Check if device is on and update the state."""
        if platform.system().lower() == "windows":
            ping_cmd = "ping -n 1 -w {} {}"\
                .format(DEFAULT_PING_TIMEOUT * 1000, self._host)
        else:
            ping_cmd = "ping -c 1 -W {} {}"\
                .format(DEFAULT_PING_TIMEOUT, self._host)

        status = sp.getstatusoutput(ping_cmd)[0]

        self._state = not bool(status)
