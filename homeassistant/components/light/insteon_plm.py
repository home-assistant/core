"""
Support for INSTEON dimmers via PowerLinc Modem.
"""
import logging
import asyncio

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light)
from homeassistant.loader import get_component
import homeassistant.util as util

DEPENDENCIES = ['insteon_plm']

_LOGGER = logging.getLogger(__name__)

@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Moo."""
    _LOGGER.info('Provisioning Insteon PLM Lights')

    plm = hass.data['insteon_plm']

    def async_insteonplm_light_callback(address = None, name = None):
        """New device detected from transport."""
        _LOGGER.info('New INSTEON PLM light device: %s (%s)', name, address)
        hass.async_add_job(async_add_devices([InsteonPLMDimmerDevice(address, name)]))

    plm.protocol.callback_new_light(async_insteonplm_light_callback)
    plm.protocol.dump_all_link_database()

    new_lights = []
    yield from async_add_devices(new_lights)

class InsteonPLMDimmerDevice(Light):
    """A Class for an Insteon device."""

    def __init__(self, address, name):
        """Initialize the light."""
        self._value = 0
        self._address = address
        self._name = name

    @property
    def name(self):
        """Return the the name of the node."""
        return self._name

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._value

    @property
    def is_on(self):
        """Return the boolean response if the node is on."""
        return self._value != 0

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    def turn_on(self, **kwargs):
        """Turn device on."""
        brightness = 100
        if ATTR_BRIGHTNESS in kwargs:
            brightness = int(kwargs[ATTR_BRIGHTNESS]) / 255 * 100

        self.node.on(brightness)

    def turn_off(self, **kwargs):
        """Turn device off."""
        self.node.off()
