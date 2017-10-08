"""
Light/LED support for the Skybell HD Doorbell.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.skybell/
"""
import logging


from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_RGB_COLOR,
    SUPPORT_BRIGHTNESS, SUPPORT_RGB_COLOR, Light)
from homeassistant.components.skybell import (
    DOMAIN as SKYBELL_DOMAIN, SkybellDevice)

DEPENDENCIES = ['skybell']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the platform for a Skybell device."""
    skybell = hass.data.get(SKYBELL_DOMAIN)

    sensors = []
    for device in skybell.get_devices():
        sensors.append(SkybellLight(device))

    add_devices(sensors, True)


def _to_skybell_level(level):
    """Convert the given HASS light level (0-255) to Skybell (0-100)."""
    return int((level * 100) / 255)


def _to_hass_level(level):
    """Convert the given Skybell (0-100) light level to HASS (0-255)."""
    return int((level * 255) / 100)


class SkybellLight(SkybellDevice, Light):
    """A binary sensor implementation for Skybell devices."""

    def __init__(self, device):
        """Initialize a light for a Skybell device."""
        super().__init__(device)
        self._name = self._device.name

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    def turn_on(self, **kwargs):
        """Turn on the light."""
        if ATTR_RGB_COLOR in kwargs:
            self._device.led_rgb = kwargs[ATTR_RGB_COLOR]
        elif ATTR_BRIGHTNESS in kwargs:
            self._device.led_intensity = _to_skybell_level(
                kwargs[ATTR_BRIGHTNESS])
        else:
            self._device.led_intensity = _to_skybell_level(255)

    def turn_off(self, **kwargs):
        """Turn off the light."""
        self._device.led_intensity = 0

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._device.led_intensity > 0

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return _to_hass_level(self._device.led_intensity)

    @property
    def rgb_color(self):
        """Return the color of the light."""
        return self._device.led_rgb

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_BRIGHTNESS | SUPPORT_RGB_COLOR
