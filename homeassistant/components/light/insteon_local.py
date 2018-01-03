"""
Support for Insteon dimmers via local hub control.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/light.insteon_local/
"""
import logging
from datetime import timedelta

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light)
import homeassistant.util as util

_CONFIGURING = {}
_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['insteon_local']
DOMAIN = 'light'

MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(milliseconds=100)
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=5)

SUPPORT_INSTEON_LOCAL = SUPPORT_BRIGHTNESS


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Insteon local light platform."""
    insteonhub = hass.data['insteon_local']
    if discovery_info is None:
        return

    linked = discovery_info['linked']
    device_list = []
    for device_id in linked:
        if linked[device_id]['cat_type'] == 'dimmer':
            device = insteonhub.dimmer(device_id)
            device_list.append(
                InsteonLocalDimmerDevice(device)
            )

    add_devices(device_list)


class InsteonLocalDimmerDevice(Light):
    """An abstract Class for an Insteon node."""

    def __init__(self, node):
        """Initialize the device."""
        self.node = node
        self._value = 0

    @property
    def name(self):
        """Return the name of the node."""
        return self.node.device_id

    @property
    def unique_id(self):
        """Return the ID of this Insteon node."""
        return 'insteon_local_{}'.format(self.node.device_id)

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._value

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update(self):
        """Update state of the light."""
        resp = self.node.status(0)

        while 'error' in resp and resp['error'] is True:
            resp = self.node.status(0)

        if 'cmd2' in resp:
            self._value = int(resp['cmd2'], 16)

    @property
    def is_on(self):
        """Return the boolean response if the node is on."""
        return self._value != 0

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_INSTEON_LOCAL

    def turn_on(self, **kwargs):
        """Turn device on."""
        brightness = 100
        if ATTR_BRIGHTNESS in kwargs:
            brightness = int(kwargs[ATTR_BRIGHTNESS]) / 255 * 100

        self.node.change_level(brightness)

    def turn_off(self, **kwargs):
        """Turn device off."""
        self.node.off()
