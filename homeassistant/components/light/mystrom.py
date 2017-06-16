"""
Support for myStrom Wifi bulbs.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.mystrom/
"""
import logging

import voluptuous as vol

from homeassistant.components.light import (
    Light, PLATFORM_SCHEMA, ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS)
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME, STATE_UNKNOWN
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['python-mystrom==0.3.8']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'myStrom bulb'

SUPPORT_MYSTROM = (SUPPORT_BRIGHTNESS)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_MAC): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the myStrom Light platform."""
    from pymystrom import MyStromBulb
    from pymystrom.exceptions import MyStromConnectionError

    host = config.get(CONF_HOST)
    mac = config.get(CONF_MAC)
    name = config.get(CONF_NAME)

    bulb = MyStromBulb(host, mac)
    try:
        if bulb.get_status()['type'] != 'rgblamp':
            _LOGGER.error("Device %s (%s) is not a myStrom bulb", host, mac)
            return False
    except MyStromConnectionError:
        _LOGGER.warning("myStrom bulb not online")

    add_devices([MyStromLight(bulb, name)], True)


class MyStromLight(Light):
    """Representation of the myStrom WiFi Bulb."""

    def __init__(self, bulb, name):
        """Initialize the light."""
        self._bulb = bulb
        self._name = name
        self._state = None
        self._available = False
        self._brightness = 0
        self._rgb_color = [0, 0, 0]

    @property
    def name(self):
        """Return the display name of this light."""
        return self._name

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_MYSTROM

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._state['on'] if self._state is not None else STATE_UNKNOWN

    def turn_on(self, **kwargs):
        """Turn on the light."""
        from pymystrom.exceptions import MyStromConnectionError

        brightness = kwargs.get(ATTR_BRIGHTNESS, 255)

        try:
            if not self.is_on:
                self._bulb.set_on()
            if brightness is not None:
                self._bulb.set_color_hsv(0, 0, round(brightness * 100 / 255))
        except MyStromConnectionError:
            _LOGGER.warning("myStrom bulb not online")

    def turn_off(self, **kwargs):
        """Turn off the bulb."""
        from pymystrom.exceptions import MyStromConnectionError

        try:
            self._bulb.set_off()
        except MyStromConnectionError:
            _LOGGER.warning("myStrom bulb not online")

    def update(self):
        """Fetch new state data for this light."""
        from pymystrom.exceptions import MyStromConnectionError

        try:
            self._state = self._bulb.get_status()
            self._brightness = int(self._bulb.get_brightness()) * 255 / 100
            self._available = True
        except MyStromConnectionError:
            _LOGGER.warning("myStrom bulb not online")
            self._available = False
