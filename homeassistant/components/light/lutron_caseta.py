"""
Support for Lutron Caseta lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.lutron_caseta/
"""
import asyncio
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_TRANSITION, SUPPORT_BRIGHTNESS,
    SUPPORT_TRANSITION, Light, DOMAIN)
from homeassistant.components.light.lutron import (
    to_hass_level, to_lutron_level)
from homeassistant.components.lutron_caseta import (
    LUTRON_CASETA_SMARTBRIDGE, LutronCasetaDevice)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['lutron_caseta']

# How many updates per second to perform when transitioning between states
TRANSITION_RATE = 2


# pylint: disable=unused-argument
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the Lutron Caseta lights."""
    devs = []
    bridge = hass.data[LUTRON_CASETA_SMARTBRIDGE]
    light_devices = bridge.get_devices_by_domain(DOMAIN)
    for light_device in light_devices:
        dev = LutronCasetaLight(light_device, bridge)
        devs.append(dev)

    async_add_devices(devs, True)


class LutronCasetaLight(LutronCasetaDevice, Light):
    """Representation of a Lutron Light, including dimmable."""

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS | SUPPORT_TRANSITION

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return to_hass_level(self._state["current_state"])

    @asyncio.coroutine
    def async_turn_on(self, **kwargs):
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
        else:
            brightness = 255
        if ATTR_TRANSITION in kwargs:
            transition = kwargs[ATTR_TRANSITION]
            yield from self.transition(transition, self.brightness, brightness)
        else:
            self._smartbridge.set_value(self._device_id,
                                        to_lutron_level(brightness))

    @asyncio.coroutine
    def transition(self, transition, from_, to):
        delta = to - from_
        step = delta / transition / TRANSITION_RATE
        for i in range(int(transition * TRANSITION_RATE)):
            step_brightness = int(max(0, from_ + (i + 1) * step))
            self._smartbridge.set_value(self._device_id,
                                        to_lutron_level(step_brightness))
            yield from asyncio.sleep(1 / TRANSITION_RATE)


    @asyncio.coroutine
    def async_turn_off(self, **kwargs):
        """Turn the light off."""
        if ATTR_TRANSITION in kwargs:
            transition = kwargs[ATTR_TRANSITION]
            yield from self.transition(transition, self.brightness, 0)
        else:
            self._smartbridge.set_value(self._device_id, 0)

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state["current_state"] > 0

    @asyncio.coroutine
    def async_update(self):
        """Call when forcing a refresh of the device."""
        self._state = self._smartbridge.get_device_by_id(self._device_id)
        _LOGGER.debug(self._state)
