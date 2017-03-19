"""Support for Lutron Caseta lights."""
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light)
from homeassistant.components.light.lutron import to_hass_level
from homeassistant.components.light.lutron import to_lutron_level
from homeassistant.components.lutron_caseta import LUTRON_CASETA_DEVICES
from homeassistant.components.lutron_caseta import LUTRON_CASETA_SMARTBRIDGE
from homeassistant.components.lutron_caseta import LutronCasetaDevice


_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup Lutron  Caseta lights."""
    devs = []
    for device in hass.data[LUTRON_CASETA_DEVICES]['light']:
        dev = LutronCasetaLight(device,
                                hass.data[LUTRON_CASETA_SMARTBRIDGE])
        devs.append(dev)

    add_devices(devs, True)
    return True


class LutronCasetaLight(LutronCasetaDevice, Light):
    """Representation of a Lutron Light, including dimmable."""

    def __init__(self, device, bridge):
        """Initialize the light."""
        self._prev_brightness = None
        LutronCasetaDevice.__init__(self, device, bridge)

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return to_hass_level(self._state["current_state"])

    def turn_on(self, **kwargs):
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs and self._device_type == "WallDimmer":
            brightness = kwargs[ATTR_BRIGHTNESS]
        else:
            brightness = 100
        self._smartbridge.set_value(self._device_id,
                                    to_lutron_level(brightness))

    def turn_off(self, **kwargs):
        """Turn the light off."""
        self._smartbridge.set_value(self._device_id, 0)

    @property
    def is_on(self):
        """Return true if device is on."""
        _LOGGER.debug(self._state)
        return self._state["current_state"] > 0

    def update(self):
        """Called when forcing a refresh of the device."""
        self._state = self._smartbridge.get_device_by_id(self._device_id)

    @property
    def should_poll(self):
        """No polling needed."""
        return False
