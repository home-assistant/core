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

    state_list = []
    
    for deviceInfo in discovery_info:
        device = deviceInfo[0]
        state = device.states[deviceInfo[1]]
       
        state_list.append(InsteonPLMDimmerDevice( hass, device, state, SUPPORT_SET_SPEED))

    async_add_devices(state_list)


class InsteonPLMDimmerDevice(Light):
    """A Class for an Insteon device."""

    def __init__(self, hass, device, state):
        """Initialize the light."""
        self._hass = hass
        self._device = device
        self._state = state

        self._state.register_updates(self.async_light_update)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def address(self):
        """Return the address of the node."""
        return self._device.address.human

    @property
    def id(self):
        """Return the name of the node."""
        return self._device.id

    @property
    def name(self):
        """Return the name of the node. (used for Entity_ID)"""
        return self._device.id + '_' + self._state.name

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        onlevel = self._state.value
        _LOGGER.debug("on level for %s is %s", self._device.address, onlevel)
        return int(onlevel)

    @property
    def is_on(self):
        """Return the boolean response if the node is on."""
        _LOGGER.debug("on level for %s is %s", self._device.id, self.brightness)
        return bool(self.brightness)

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    @property
    def device_state_attributes(self):
        """Provide attributes for display on device card."""
        insteon_plm = get_component('insteon_plm')
        return insteon_plm.common_attributes(self._device, self._state)

    @callback
    def async_light_update(self, entity_id, statename, val):
        """Receive notification from transport that new data exists."""
        _LOGGER.info("Received update calback from PLM for %s", self.id)
        self._hass.async_add_job(self.async_update_ha_state())

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn device on."""
        if ATTR_BRIGHTNESS in kwargs:
            brightness = int(kwargs[ATTR_BRIGHTNESS])
            self._state.set_level(brightness)
        else:
            self._state.on()

    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn device off."""
        self._state.off()
