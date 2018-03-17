"""
Support for Insteon lights via PowerLinc Modem.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/light.insteon_plm/
"""
import asyncio
import logging

from homeassistant.components.insteon_plm import InsteonPLMEntity
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['insteon_plm']

MAX_BRIGHTNESS = 255


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Insteon PLM device."""
    plm = hass.data['insteon_plm']

    address = discovery_info['address']
    device = plm.devices[address]
    state_key = discovery_info['state_key']

    _LOGGER.debug('Adding device %s entity %s to Light platform',
                  device.address.hex, device.states[state_key].name)

    new_entity = InsteonPLMDimmerDevice(device, state_key)

    async_add_devices([new_entity])


class InsteonPLMDimmerDevice(InsteonPLMEntity, Light):
    """A Class for an Insteon device."""

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        onlevel = self._insteon_device_state.value
        return int(onlevel)

    @property
    def is_on(self):
        """Return the boolean response if the node is on."""
        return bool(self.brightness)

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn device on."""
        if ATTR_BRIGHTNESS in kwargs:
            brightness = int(kwargs[ATTR_BRIGHTNESS])
            self._insteon_device_state.set_level(brightness)
        else:
            self._insteon_device_state.on()

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn device off."""
        self._insteon_device_state.off()
