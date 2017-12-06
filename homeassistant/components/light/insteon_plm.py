"""
Support for Insteon lights via PowerLinc Modem.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/insteon_plm/
"""
import logging
import asyncio

from homeassistant.core import callback
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light)
from homeassistant.loader import get_component

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['insteon_plm']

MAX_BRIGHTNESS = 255


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Insteon PLM device."""
    plm = hass.data['insteon_plm']

    device_list = []
    for device in discovery_info:
        name = device.get('address')
        address = device.get('address_hex')
        dimmable = bool('dimmable' in device.get('capabilities'))

        _LOGGER.info("Registered %s with light platform", name)

        device_list.append(
            InsteonPLMDimmerDevice(hass, plm, address, name, dimmable)
        )

    async_add_devices(device_list)


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
            self.async_light_update, {'address': self._address})

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def address(self):
        """Return the address of the node."""
        return self._address

    @property
    def name(self):
        """Return the name of the node."""
        return self._name

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        onlevel = self._plm.get_device_attr(self._address, 'onlevel')
        _LOGGER.debug("on level for %s is %s", self._address, onlevel)
        return int(onlevel)

    @property
    def is_on(self):
        """Return the boolean response if the node is on."""
        onlevel = self._plm.get_device_attr(self._address, 'onlevel')
        _LOGGER.debug("on level for %s is %s", self._address, onlevel)
        return bool(onlevel)

    @property
    def supported_features(self):
        """Flag supported features."""
        if self._dimmable:
            return SUPPORT_BRIGHTNESS

    @property
    def device_state_attributes(self):
        """Provide attributes for display on device card."""
        insteon_plm = get_component('insteon_plm')
        return insteon_plm.common_attributes(self)

    def get_attr(self, key):
        """Return specified attribute for this device."""
        return self._plm.get_device_attr(self.address, key)

    @callback
    def async_light_update(self, message):
        """Receive notification from transport that new data exists."""
        _LOGGER.info("Received update calback from PLM for %s", self._address)
        self._hass.async_add_job(self.async_update_ha_state())

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn device on."""
        if ATTR_BRIGHTNESS in kwargs:
            brightness = int(kwargs[ATTR_BRIGHTNESS])
        else:
            brightness = MAX_BRIGHTNESS
        self._plm.turn_on(self._address, brightness=brightness)

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn device off."""
        self._plm.turn_off(self._address)
