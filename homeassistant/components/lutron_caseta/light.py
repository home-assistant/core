"""Support for Lutron Caseta lights."""
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, DOMAIN, SUPPORT_BRIGHTNESS, Light)
from homeassistant.components.lutron.light import (
    to_hass_level, to_lutron_level)

from . import LUTRON_CASETA_SMARTBRIDGE, LutronCasetaDevice

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['lutron_caseta']


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the Lutron Caseta lights."""
    devs = []
    bridge = hass.data[LUTRON_CASETA_SMARTBRIDGE]
    light_devices = bridge.get_devices_by_domain(DOMAIN)
    for light_device in light_devices:
        dev = LutronCasetaLight(light_device, bridge)
        devs.append(dev)

    async_add_entities(devs, True)


class LutronCasetaLight(LutronCasetaDevice, Light):
    """Representation of a Lutron Light, including dimmable."""

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return to_hass_level(self._state["current_state"])

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
        self._smartbridge.set_value(self._device_id,
                                    to_lutron_level(brightness))

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        self._smartbridge.set_value(self._device_id, 0)

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state["current_state"] > 0

    async def async_update(self):
        """Call when forcing a refresh of the device."""
        self._state = self._smartbridge.get_device_by_id(self._device_id)
        _LOGGER.debug(self._state)
