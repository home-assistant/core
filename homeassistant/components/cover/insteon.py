"""
Support for Insteon lights via PowerLinc Modem.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/light.insteon/
"""
import asyncio
import logging

from homeassistant.components.insteon import InsteonEntity
from homeassistant.components.cover import (CoverDevice, ATTR_POSITION,
                                            SUPPORT_OPEN, SUPPORT_CLOSE,
                                            SUPPORT_SET_POSITION)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['insteon']


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Insteon component."""
    insteon_modem = hass.data['insteon'].get('modem')

    address = discovery_info['address']
    device = insteon_modem.devices[address]
    state_key = discovery_info['state_key']

    _LOGGER.debug('Adding device %s entity %s to Light platform',
                  device.address.hex, device.states[state_key].name)

    new_entity = InsteonDimmerDevice(device, state_key)

    async_add_devices([new_entity])



class InsteonCoverDevice(InsteonEntity, CoverDevice):
    """A Class for an Insteon device."""

    @property
    def is_closed(self):
        """Return the boolean response if the node is on."""
        return bool(self.brightness)

    @asyncio.coroutine
    def async_open_cover(self, **kwargs):
        """Open device."""
        if ATTR_POSITION in kwargs:
            brightness = int(kwargs[ATTR_POSITION])
            self._insteon_device_state.set_level(brightness)
        else:
            self._insteon_device_state.open()

    @asyncio.coroutine
    def async_close_cover(self, **kwargs):
        """Close device."""
        self._insteon_device_state.close()

    @asyncio.coroutine
    def async_set_cover_position(self, **kwargs):
        """Set the cover position."""
        await async_open_cover(**kwargs)