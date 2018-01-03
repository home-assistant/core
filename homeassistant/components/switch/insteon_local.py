"""
Support for Insteon switch devices via local hub support.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/switch.insteon_local/
"""
import logging
from datetime import timedelta

from homeassistant.components.switch import SwitchDevice
import homeassistant.util as util

_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['insteon_local']
DOMAIN = 'switch'

MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(milliseconds=100)
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Insteon local switch platform."""
    insteonhub = hass.data['insteon_local']
    if discovery_info is None:
        return

    linked = discovery_info['linked']
    device_list = []
    for device_id in linked:
        if linked[device_id]['cat_type'] == 'switch':
            device = insteonhub.switch(device_id)
            device_list.append(
                InsteonLocalSwitchDevice(device)
            )

    add_devices(device_list)


class InsteonLocalSwitchDevice(SwitchDevice):
    """An abstract Class for an Insteon node."""

    def __init__(self, node):
        """Initialize the device."""
        self.node = node
        self._state = False

    @property
    def name(self):
        """Return the name of the node."""
        return self.node.device_id

    @property
    def unique_id(self):
        """Return the ID of this Insteon node."""
        return 'insteon_local_{}'.format(self.node.device_id)

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update(self):
        """Get the updated status of the switch."""
        resp = self.node.status(0)

        while 'error' in resp and resp['error'] is True:
            resp = self.node.status(0)

        if 'cmd2' in resp:
            self._state = int(resp['cmd2'], 16) > 0

    @property
    def is_on(self):
        """Return the boolean response if the node is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn device on."""
        self.node.on()
        self._state = True

    def turn_off(self, **kwargs):
        """Turn device off."""
        self.node.off()
        self._state = False
