"""
Support for Homematic lighs.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.homematic/
"""
import logging
from homeassistant.components.light import (ATTR_BRIGHTNESS,
                                            SUPPORT_BRIGHTNESS, Light)
from homeassistant.const import STATE_UNKNOWN
import homeassistant.components.homematic as homematic

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['homematic']

SUPPORT_HOMEMATIC = SUPPORT_BRIGHTNESS


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Homematic light platform."""
    if discovery_info is None:
        return

    return homematic.setup_hmdevice_discovery_helper(
        HMLight,
        discovery_info,
        add_devices
    )


class HMLight(homematic.HMDevice, Light):
    """Representation of a Homematic light."""

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        if not self.available:
            return None
        # Is dimmer?
        if self._state is "LEVEL":
            return int(self._hm_get_state() * 255)
        else:
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
        if not self.available:
            return

        if ATTR_BRIGHTNESS in kwargs and self._state is "LEVEL":
            percent_bright = float(kwargs[ATTR_BRIGHTNESS]) / 255
            self._hmdevice.set_level(percent_bright, self._channel)
        else:
            self._hmdevice.on(self._channel)

    def turn_off(self, **kwargs):
        """Turn the light off."""
        if self.available:
            self._hmdevice.off(self._channel)

    def _init_data_struct(self):
        """Generate a data dict (self._data) from the Homematic metadata."""
        # Use LEVEL
        self._state = "LEVEL"
        self._data.update({self._state: STATE_UNKNOWN})
