"""
Support for ISY994 lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/isy994/
"""
import logging

from homeassistant.components.isy994 import (
    HIDDEN_STRING, ISY, SENSOR_STRING, ISYDeviceABC)
from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.const import STATE_OFF, STATE_ON


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the ISY994 platform."""
    logger = logging.getLogger(__name__)
    devs = []

    if ISY is None or not ISY.connected:
        logger.error('A connection has not been made to the ISY controller.')
        return False

    # Import dimmable nodes
    for (path, node) in ISY.nodes:
        if node.dimmable and SENSOR_STRING not in node.name:
            if HIDDEN_STRING in path:
                node.name += HIDDEN_STRING
            devs.append(ISYLightDevice(node))

    add_devices(devs)


class ISYLightDevice(ISYDeviceABC):
    """Representation of a ISY light."""

    _domain = 'light'
    _dtype = 'analog'
    _attrs = {ATTR_BRIGHTNESS: 'value'}
    _onattrs = [ATTR_BRIGHTNESS]
    _states = [STATE_ON, STATE_OFF]

    def _attr_filter(self, attr):
        """Filter brightness out of entity while off."""
        if ATTR_BRIGHTNESS in attr and not self.is_on:
            del attr[ATTR_BRIGHTNESS]
        return attr
