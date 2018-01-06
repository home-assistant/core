"""
Support for Vera lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.vera/
"""
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_HS_COLOR, ENTITY_ID_FORMAT,
    SUPPORT_BRIGHTNESS, SUPPORT_COLOR, Light)
from homeassistant.components.vera import (
    VERA_CONTROLLER, VERA_DEVICES, VeraDevice)
import homeassistant.util.color as color_util

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['vera']


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Vera lights."""
    add_devices(
        VeraLight(device, hass.data[VERA_CONTROLLER]) for
        device in hass.data[VERA_DEVICES]['light'])


class VeraLight(VeraDevice, Light):
    """Representation of a Vera Light, including dimmable."""

    def __init__(self, vera_device, controller):
        """Initialize the light."""
        self._state = False
        self._color = None
        self._brightness = None
        VeraDevice.__init__(self, vera_device, controller)
        self.entity_id = ENTITY_ID_FORMAT.format(self.vera_id)

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

    @property
    def hs_color(self):
        """Return the color of the light."""
        return self._color

    @property
    def supported_features(self):
        """Flag supported features."""
        if self._color:
            return SUPPORT_BRIGHTNESS | SUPPORT_COLOR
        return SUPPORT_BRIGHTNESS

    def turn_on(self, **kwargs):
        """Turn the light on."""
        if ATTR_HS_COLOR in kwargs and self._color:
            rgb = color_util.color_hs_to_RGB(*kwargs[ATTR_HS_COLOR])
            self.vera_device.set_color(rgb)
        elif ATTR_BRIGHTNESS in kwargs and self.vera_device.is_dimmable:
            self.vera_device.set_brightness(kwargs[ATTR_BRIGHTNESS])
        else:
            self.vera_device.switch_on()

        self._state = True
        self.schedule_update_ha_state(True)

    def turn_off(self, **kwargs):
        """Turn the light off."""
        self.vera_device.switch_off()
        self._state = False
        self.schedule_update_ha_state()

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def update(self):
        """Call to update state."""
        self._state = self.vera_device.is_switched_on()
        if self.vera_device.is_dimmable:
            # If it is dimmable, both functions exist. In case color
            # is not supported, it will return None
            self._brightness = self.vera_device.get_brightness()
            rgb = self.vera_device.get_color()
            self._color = color_util.color_RGB_to_hs(*rgb) if rgb else None
