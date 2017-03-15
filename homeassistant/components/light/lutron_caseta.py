"""Support for Lutron Caseta lights."""
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, DOMAIN, SUPPORT_BRIGHTNESS, Light)
from homeassistant.components.lutron_caseta import (
    LUTRON_CASETA_DEVICES, LUTRON_CASETA_SMARTBRIDGE)
from homeassistant.components.light.lutron import to_hass_level
from homeassistant.components.light.lutron import to_lutron_level

DEPENDENCIES = ['lutron_caseta']

_LOGGER = logging.getLogger(__name__)

def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup Lutron lights."""
    devs = []
    for _caseta_light in hass.data[LUTRON_CASETA_DEVICES]['light']:
        dev = LutronCasetaLight(hass, _caseta_light,
                          hass.data[LUTRON_CASETA_SMARTBRIDGE])
        devs.append(dev)
    add_devices(devs, True)

    return True


class LutronCasetaLight(Light):
    """Representation of a Lutron Light, including dimmable."""

    def __init__(self, hass, device_info, smartbridge):
        """Initialize the light."""
        self._prev_brightness = None
        self._device_id = device_info["device_id"]
        self._device_type = device_info["type"]
        self._device_name = device_info["name"]
        self._state = None
        self._smartbridge = smartbridge
        self.update()


    @property
    def name(self):
        """Return the name of the device."""
        return self._device_name

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return to_hass_level(self._state["value"])

    def turn_on(self, **kwargs):
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs and self._device_type == "WallDimmer":
            brightness = kwargs[ATTR_BRIGHTNESS]
        else:
            brightness = 100
        self._state = self._smartbridge.set_value(self._device_id, brightness)

    def turn_off(self, **kwargs):
        """Turn the light off."""
        self._state = self._smartbridge.set_value(self._device_id, 0)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attr = {}
        attr['Lutron Integration ID'] = self._device_id
        return attr

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state["value"] > 0

    def update(self):
        """Called when forcing a refresh of the device."""
        self._state = self._smartbridge.get_state(self._device_id)
