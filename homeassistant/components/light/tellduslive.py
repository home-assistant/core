"""
Support for Tellstick switches using Tellstick Net.

This platform uses the Telldus Live online service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.tellduslive/
"""
import logging

from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light)
from homeassistant.components.tellduslive import TelldusLiveEntity

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Tellstick Net lights."""
    if discovery_info is None:
        return
    add_devices(TelldusLiveLight(hass, light) for light in discovery_info)


class TelldusLiveLight(TelldusLiveEntity, Light):
    """Representation of a Tellstick Net light."""

    def __init__(self, hass, device_id):
        """Initialize the  Tellstick Net light."""
        super().__init__(hass, device_id)
        self._last_brightness = self.brightness

    def changed(self):
        """Define a property of the device that might have changed."""
        self._last_brightness = self.brightness
        super().changed()

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self.device.dim_level

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS

    @property
    def is_on(self):
        """Return true if light is on."""
        return self.device.is_on

    def turn_on(self, **kwargs):
        """Turn the light on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS, self._last_brightness)
        self.device.dim(level=brightness)
        self.changed()

    def turn_off(self, **kwargs):
        """Turn the light off."""
        self.device.turn_off()
        self.changed()
