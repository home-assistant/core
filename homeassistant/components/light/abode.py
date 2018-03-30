"""
This component provides HA light support for Abode Security System.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.abode/
"""
import logging

from homeassistant.components.abode import AbodeDevice, DOMAIN as ABODE_DOMAIN
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_HS_COLOR,
    SUPPORT_BRIGHTNESS, SUPPORT_COLOR, Light)
import homeassistant.util.color as color_util


DEPENDENCIES = ['abode']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Abode light devices."""
    import abodepy.helpers.constants as CONST

    data = hass.data[ABODE_DOMAIN]

    device_types = [CONST.TYPE_LIGHT, CONST.TYPE_SWITCH]

    devices = []

    # Get all regular lights that are not excluded or switches marked as lights
    for device in data.abode.get_devices(generic_type=device_types):
        if data.is_excluded(device) or not data.is_light(device):
            continue

        devices.append(AbodeLight(data, device))

    data.devices.extend(devices)

    add_devices(devices)


class AbodeLight(AbodeDevice, Light):
    """Representation of an Abode light."""

    def turn_on(self, **kwargs):
        """Turn on the light."""
        if (ATTR_HS_COLOR in kwargs and
                self._device.is_dimmable and self._device.has_color):
            self._device.set_color(color_util.color_hs_to_RGB(
                *kwargs[ATTR_HS_COLOR]))

        if ATTR_BRIGHTNESS in kwargs and self._device.is_dimmable:
            self._device.set_level(kwargs[ATTR_BRIGHTNESS])
        else:
            self._device.switch_on()

    def turn_off(self, **kwargs):
        """Turn off the light."""
        self._device.switch_off()

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._device.is_on

    @property
    def brightness(self):
        """Return the brightness of the light."""
        if self._device.is_dimmable and self._device.has_brightness:
            return self._device.brightness

    @property
    def hs_color(self):
        """Return the color of the light."""
        if self._device.is_dimmable and self._device.has_color:
            return color_util.color_RGB_to_hs(*self._device.color)

    @property
    def supported_features(self):
        """Flag supported features."""
        if self._device.is_dimmable and self._device.has_color:
            return SUPPORT_BRIGHTNESS | SUPPORT_COLOR
        elif self._device.is_dimmable:
            return SUPPORT_BRIGHTNESS

        return 0
