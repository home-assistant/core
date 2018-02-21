"""
Support for Insteon lights via PowerLinc Modem.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/light.insteon_plm/
"""
import asyncio
import logging

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
    entities = []
    plm = hass.data['insteon_plm']
    _LOGGER.debug("Got here light")
    _LOGGER.debug(discovery_info)

    address = discovery_info['address']
    device = plm.devices[address]
    state_key = discovery_info['state_key']

    _LOGGER.debug('Adding device %s with state name %s to Light platform.', 
                  device.address.hex, device.states[state_key].name)

    entities.append(InsteonPLMDimmerDevice(device, state_key))

    async_add_devices(entities)


class InsteonPLMDimmerDevice(Light):
    """A Class for an Insteon device."""

    def __init__(self, device, state_key):
        """Initialize the light."""
        self._insteon_device_state = device.states[state_key]
        self._insteon_device = device

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def address(self):
        """Return the address of the node."""
        return self._insteon_device.address.human

    def group(self):
        """Return the INSTEON group that the entity responds to."""
        return self._insteon_device_state.group

    @property
    def name(self):
        """Return the name of the node (used for Entity_ID)."""
        name = ''
        if self._insteon_device_state.group == 0x01:
            name = self._insteon_device.id
        else:
            name = '{:s}_{:d}'.format(self._insteon_device.id,
                                      self._insteon_device_state.group)
        return name

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

    @property
    def device_state_attributes(self):
        """Provide attributes for display on device card."""
        insteon_plm = get_component('insteon_plm')
        return insteon_plm.common_attributes(self)

    @callback
    def async_light_update(self, entity_id, statename, val):
        """Receive notification from transport that new data exists."""
        self.async_schedule_update_ha_state()

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

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register INSTEON update events."""
        self._insteon_device_state.register_updates(self.async_light_update)
