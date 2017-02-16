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

    def async_insteonplm_light_callback(device):
        """New device detected from transport."""
        name = device['address']
        address = device['address_hex']

        if 'dimmable' in device['capabilities']:
            dimmable = True
        else:
            dimmable = False

        _LOGGER.info('New INSTEON PLM light device: %s (%s)', name, address)
        hass.async_add_job(async_add_devices([InsteonPLMDimmerDevice(hass, plm, address, name, dimmable)]))

    criteria = dict(capability='light')
    plm.protocol.add_device_callback(async_insteonplm_light_callback, criteria)


    new_lights = []
    yield from async_add_devices(new_lights)

class InsteonPLMDimmerDevice(Light):
    """A Class for an Insteon device."""

    def __init__(self, hass, plm, address, name, dimmable):
        """Initialize the light."""
        self._hass = hass
        self._plm = plm.protocol
        self._address = address
        self._name = name
        self._dimmable = dimmable

        self._plm.add_update_callback(
            self.async_insteonplm_light_update_callback,
            dict(address=self._address))

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the the name of the node."""
        return self._name

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        onlevel = self._plm.get_device_attr(self._address, 'onlevel')
        _LOGGER.debug('on level for %s is %s', self._address, onlevel)
        return int(onlevel)

    @property
    def is_on(self):
        """Return the boolean response if the node is on."""
        onlevel = self._plm.get_device_attr(self._address, 'onlevel')
        _LOGGER.debug('on level for %s is %s', self._address, onlevel)
        if onlevel:
            return (onlevel > 0)
        else:
            return False

    @property
    def supported_features(self):
        """Flag supported features."""
        if self._dimmable:
            return SUPPORT_BRIGHTNESS

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn device on."""
        if ATTR_BRIGHTNESS in kwargs:
            brightness = int(kwargs[ATTR_BRIGHTNESS])
        else:
            brightness = 255
        self._plm.turn_on(self._address, brightness=brightness)

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn device off."""
        self._plm.turn_off(self._address)

    def async_insteonplm_light_update_callback(self, message):
        """Receive notification from transport that new data exists."""
        _LOGGER.info('Received update calback from PLM for %s', self._address)
        self._hass.async_add_job(self.async_update_ha_state(True))
