"""
Support for Tikteck lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.tikteck/
"""
import logging

import voluptuous as vol

from homeassistant.const import CONF_DEVICES, CONF_NAME, CONF_PASSWORD
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_RGB_COLOR, SUPPORT_BRIGHTNESS, SUPPORT_RGB_COLOR,
    Light, PLATFORM_SCHEMA)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['tikteck==0.4']

_LOGGER = logging.getLogger(__name__)

SUPPORT_TIKTECK_LED = (SUPPORT_BRIGHTNESS | SUPPORT_RGB_COLOR)

DEVICE_SCHEMA = vol.Schema({
    vol.Optional(CONF_NAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_DEVICES, default={}): {cv.string: DEVICE_SCHEMA},
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Tikteck platform."""
    lights = []
    for address, device_config in config[CONF_DEVICES].items():
        device = {}
        device['name'] = device_config[CONF_NAME]
        device['password'] = device_config[CONF_PASSWORD]
        device['address'] = address
        light = TikteckLight(device)
        if light.is_valid:
            lights.append(light)

    add_devices(lights)


class TikteckLight(Light):
    """Representation of a Tikteck light."""

    def __init__(self, device):
        """Initialize the light."""
        import tikteck

        self._name = device['name']
        self._address = device['address']
        self._password = device['password']
        self._brightness = 255
        self._rgb = [255, 255, 255]
        self._state = False
        self.is_valid = True
        self._bulb = tikteck.tikteck(
            self._address, "Smart Light", self._password)
        if self._bulb.connect() is False:
            self.is_valid = False
            _LOGGER.error(
                "Failed to connect to bulb %s, %s", self._address, self._name)

    @property
    def unique_id(self):
        """Return the ID of this light."""
        return "{}.{}".format(self.__class__, self._address)

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
    def rgb_color(self):
        """Return the color property."""
        return self._rgb

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_TIKTECK_LED

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def assumed_state(self):
        """Return the assumed state."""
        return True

    def set_state(self, red, green, blue, brightness):
        """Set the bulb state."""
        return self._bulb.set_state(red, green, blue, brightness)

    def turn_on(self, **kwargs):
        """Turn the specified light on."""
        self._state = True

        rgb = kwargs.get(ATTR_RGB_COLOR)
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        if rgb is not None:
            self._rgb = rgb
        if brightness is not None:
            self._brightness = brightness

        self.set_state(self._rgb[0], self._rgb[1], self._rgb[2],
                       self.brightness)
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the specified light off."""
        self._state = False
        self.set_state(0, 0, 0, 0)
        self.schedule_update_ha_state()
