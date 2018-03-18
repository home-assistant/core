"""
Support for the Roku remote.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/remote.roku/
"""

from homeassistant.components import remote
from homeassistant.const import (
    CONF_NAME, CONF_HOST)

DEPENDENCIES = ['roku']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Roku remote platform."""
    if not discovery_info:
        return

    name = discovery_info[CONF_NAME]
    host = discovery_info[CONF_HOST]
    add_devices([RokuRemote(host, name)])


class RokuRemote(remote.RemoteDevice):
    """Representation of a Roku remote on the network."""

    def __init__(self, host, name):
        """Initialize the Roku device."""
        from roku import Roku

        self._roku = Roku(host)
        self._name = name
        self._unique_id = self._roku.device_info.sernum

    @property
    def should_poll(self):
        """Device should not be polled."""
        return False

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self):
        """Return an unique ID."""
        return self._unique_id

    @property
    def is_on(self):
        """Return true if device is on."""
        return True

    def send_command(self, command, **kwargs):
        """Send a command to one device."""
        # Send commands in specified order but schedule only one coroutine
        def _send_commands():
            for single_command in command:
                if not hasattr(self._roku, single_command):
                    continue

                getattr(self._roku, single_command)()

        _send_commands()
