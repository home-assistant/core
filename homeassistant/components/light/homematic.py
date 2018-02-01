"""
Support for Homematic lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.homematic/
"""
import logging
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light)
from homeassistant.components.homematic import HMDevice, ATTR_DISCOVER_DEVICES
from homeassistant.const import STATE_UNKNOWN

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['homematic']

SUPPORT_HOMEMATIC = SUPPORT_BRIGHTNESS


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Homematic light platform."""
    if discovery_info is None:
        return

    devices = []
    for conf in discovery_info[ATTR_DISCOVER_DEVICES]:
        new_device = HMLight(conf)
        devices.append(new_device)

    add_devices(devices)


class HMLight(HMDevice, Light):
    """Representation of a Homematic light."""

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        # Is dimmer?
        if self._state == "LEVEL":
            return int(self._hm_get_state() * 255)
        return None

    @property
    def is_on(self):
        """Return true if light is on."""
        try:
            return self._hm_get_state() > 0
        except TypeError:
            return False

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_HOMEMATIC

    def turn_on(self, **kwargs):
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs and self._state == "LEVEL":
            percent_bright = float(kwargs[ATTR_BRIGHTNESS]) / 255
            self._hmdevice.set_level(percent_bright, self._channel)
        else:
            self._hmdevice.on(self._channel)

    def turn_off(self, **kwargs):
        """Turn the light off."""
        self._hmdevice.off(self._channel)

    def _init_data_struct(self):
        """Generate a data dict (self._data) from the Homematic metadata."""
        # Use LEVEL
        self._state = "LEVEL"
        self._data.update({self._state: STATE_UNKNOWN})
