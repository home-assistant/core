"""Support for the Roku remote."""
import requests.exceptions

from homeassistant.components import remote
from homeassistant.const import (CONF_HOST)


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the Roku remote platform."""
    if not discovery_info:
        return

    host = discovery_info[CONF_HOST]
    async_add_entities([RokuRemote(host)], True)


class RokuRemote(remote.RemoteDevice):
    """Device that sends commands to an Roku."""

    def __init__(self, host):
        """Initialize the Roku device."""
        from roku import Roku

        self.roku = Roku(host)
        self._device_info = {}

    def update(self):
        """Retrieve latest state."""
        try:
            self._device_info = self.roku.device_info
        except (requests.exceptions.ConnectionError,
                requests.exceptions.ReadTimeout):
            pass

    @property
    def name(self):
        """Return the name of the device."""
        if self._device_info.userdevicename:
            return self._device_info.userdevicename
        return "Roku {}".format(self._device_info.sernum)

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._device_info.sernum

    @property
    def is_on(self):
        """Return true if device is on."""
        return True

    @property
    def should_poll(self):
        """No polling needed for Roku."""
        return False

    def send_command(self, command, **kwargs):
        """Send a command to one device."""
        for single_command in command:
            if not hasattr(self.roku, single_command):
                continue

            getattr(self.roku, single_command)()
