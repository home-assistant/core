"""
Support for FutureNow Ethernet unit outputs as Lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.futurenow/
"""

import logging

import voluptuous as vol

from homeassistant.const import (
    CONF_NAME, CONF_HOST, CONF_PORT, CONF_DEVICES)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, Light,
    PLATFORM_SCHEMA)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pyfnip==0.2']

_LOGGER = logging.getLogger(__name__)

CONF_DRIVER = 'driver'
CONF_DRIVER_FNIP6X10AD = 'FNIP6x10ad'
CONF_DRIVER_FNIP8X10A = 'FNIP8x10a'
CONF_DRIVER_TYPES = [CONF_DRIVER_FNIP6X10AD, CONF_DRIVER_FNIP8X10A]

DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Optional('dimmable', default=False): cv.boolean,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DRIVER): vol.In(CONF_DRIVER_TYPES),
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PORT): cv.port,
    vol.Required(CONF_DEVICES): {cv.string: DEVICE_SCHEMA},
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the light platform for each FutureNow unit."""
    lights = []
    for channel, device_config in config[CONF_DEVICES].items():
        device = {}
        device['name'] = device_config[CONF_NAME]
        device['dimmable'] = device_config['dimmable']
        device['channel'] = channel
        device['driver'] = config[CONF_DRIVER]
        device['host'] = config[CONF_HOST]
        device['port'] = config[CONF_PORT]
        lights.append(FutureNowLight(device))

    add_devices(lights, True)


def to_futurenow_level(level):
    """Convert the given HASS light level (0-255) to FutureNow (0-100)."""
    return int((level * 100) / 255)


def to_hass_level(level):
    """Convert the given FutureNow (0-100) light level to HASS (0-255)."""
    return int((level * 255) / 100)


class FutureNowLight(Light):
    """Representation of an FutureNow light."""

    def __init__(self, device):
        """Initialize the light."""
        import pyfnip

        self._name = device['name']
        self._dimmable = device['dimmable']
        self._channel = device['channel']
        self._brightness = None
        self._last_brightness = 255
        self._state = None

        if device['driver'] == CONF_DRIVER_FNIP6X10AD:
            self._light = pyfnip.FNIP6x2adOutput(device['host'],
                                                 device['port'],
                                                 self._channel)
        if device['driver'] == CONF_DRIVER_FNIP8X10A:
            self._light = pyfnip.FNIP8x10aOutput(device['host'],
                                                 device['port'],
                                                 self._channel)

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def supported_features(self):
        """Flag supported features."""
        if self._dimmable:
            return SUPPORT_BRIGHTNESS
        return 0

    def turn_on(self, **kwargs):
        """Turn the light on."""
        if self._dimmable:
            level = kwargs.get(ATTR_BRIGHTNESS, self._last_brightness)
        else:
            level = 255
        self._light.turn_on(to_futurenow_level(level))

    def turn_off(self, **kwargs):
        """Turn the light off."""
        self._light.turn_off()
        if self._brightness:
            self._last_brightness = self._brightness

    def update(self):
        """Fetch new state data for this light."""
        state = int(self._light.is_on())
        self._state = bool(state)
        self._brightness = to_hass_level(state)
