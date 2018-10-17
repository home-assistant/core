"""
Support for the Roku remote.
 For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/remote.roku/
"""

from homeassistant.components import remote
from homeassistant.const import (CONF_NAME, CONF_HOST)


DEPENDENCIES = ['roku']


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up the Apple TV remote platform."""
    if not discovery_info:
        return

    name = discovery_info[CONF_NAME]
    host = discovery_info[CONF_HOST]
    async_add_entities([RokuRemote(host, name)])


class RokuRemote(remote.RemoteDevice):
    """Device that sends commands to an Apple TV."""

    def __init__(self, host, name):
        """Initialize the Roku device."""
        from roku import Roku

        self._roku = Roku(host)
        self._name = name
        self._unique_id = self._roku.device_info.sernum

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def is_on(self):
        return True

    @property
    def should_poll(self):
        """No polling needed for Apple TV."""
        return False

    def send_command(self, command, **kwargs):
        """Send a command to one device."""
        for single_command in command:
            if not hasattr(self._roku, single_command):
                continue

            getattr(self._roku, single_command)()
