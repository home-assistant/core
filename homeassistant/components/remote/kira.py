"""
Support for Keene Electronics IR-IP devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/remote.kira/
"""
import logging
import functools as ft

import homeassistant.components.remote as remote
from homeassistant.helpers.entity import Entity

from homeassistant.const import (
    STATE_UNKNOWN,
    CONF_DEVICE,
    CONF_NAME)

DOMAIN = 'kira'

_LOGGER = logging.getLogger(__name__)

CONF_REMOTE = "remote"


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Kira platform."""
    if discovery_info:
        name = discovery_info.get(CONF_NAME)
        device = discovery_info.get(CONF_DEVICE)

        kira = hass.data[DOMAIN][CONF_REMOTE][name]
        add_devices([KiraRemote(device, kira)])
    return True


class KiraRemote(Entity):
    """Remote representation used to send commands to a Kira device."""

    def __init__(self, name, kira):
        """Initialize KiraRemote class."""
        _LOGGER.debug("KiraRemote device init started for: %s", name)
        self._name = name
        self._state = STATE_UNKNOWN

        self._kira = kira

    @property
    def name(self):
        """Return the Kira device's name."""
        return self._name

    @property
    def device_state_attributes(self):
        """Add platform specific attributes."""
        return {}

    @property
    def is_on(self):
        """Return True. Power state doesn't apply to this device."""
        return True

    def update(self):
        """No-op."""

    def send_command(self, **kwargs):
        """Send a command to one device."""
        for command in kwargs.get(remote.ATTR_COMMAND):
            code_tuple = (command,
                          kwargs.get(remote.ATTR_DEVICE))
            _LOGGER.info("Sending Command: %s to %s", *code_tuple)
            self._kira.sendCode(code_tuple)

    def async_send_command(self, **kwargs):
        """Send a command to a device.

        This method must be run in the event loop and returns a coroutine.
        """
        return self.hass.async_add_job(ft.partial(self.send_command, **kwargs))
