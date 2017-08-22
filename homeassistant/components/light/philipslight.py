"""
Support for Xiaomi Philips Lights (LED Ball & Ceil).

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/light.philipslight/
"""
import logging
import math

import voluptuous as vol

from homeassistant.util.color import (
    color_temperature_kelvin_to_mired as kelvin_to_mired, )

import homeassistant.helpers.config_validation as cv
from homeassistant.components.light import (
    PLATFORM_SCHEMA, ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS,
    ATTR_COLOR_TEMP, SUPPORT_COLOR_TEMP, Light, )

from homeassistant.const import (DEVICE_DEFAULT_NAME, CONF_NAME,
                                 CONF_HOST, CONF_TOKEN, )

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_TOKEN): vol.All(str, vol.Length(min=32, max=32)),
    vol.Optional(CONF_NAME): cv.string,
})

REQUIREMENTS = ['python-mirobo==0.1.3']

# The light does not accept cct values < 1
CCT_MIN = 1
CCT_MAX = 100

SUCCESS = ['ok']


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Set up the light from config."""
    host = config.get(CONF_HOST)
    name = config.get(CONF_NAME)
    token = config.get(CONF_TOKEN)

    add_devices_callback([PhilipsLight(name, host, token)], True)


class PhilipsLight(Light):
    """Representation of a Philips Light."""

    def __init__(self, name, host, token):
        """Initialize the light device."""
        self._name = name or DEVICE_DEFAULT_NAME
        self.host = host
        self.token = token

        self._brightness = 180
        self._color_temp = None

        self._light = None
        self._state = None

    @property
    def should_poll(self):
        """Poll the light."""
        return True

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def available(self):
        """Return true when state is known."""
        return self._state is not None

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._state

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def color_temp(self):
        """Return the color temperature."""
        return self._color_temp

    @property
    def min_mireds(self):
        """Return the coldest color_temp that this light supports."""
        return math.floor(kelvin_to_mired(5700))

    @property
    def max_mireds(self):
        """Return the warmest color_temp that this light supports."""
        return math.floor(kelvin_to_mired(3000))

    @property
    def supported_features(self):
        """Return the supported features."""
        return SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP

    @property
    def light(self):
        """Property accessor for light object."""
        if not self._light:
            from mirobo import Ceil
            _LOGGER.info("Initializing light with host %s", self.host)
            self._light = Ceil(self.host, self.token)

        return self._light

    def turn_on(self, **kwargs):
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs:
            self._brightness = kwargs[ATTR_BRIGHTNESS]

            percent_brightness = int(100 * self._brightness / 255)

            if self.light.set_bright(percent_brightness) == SUCCESS:
                _LOGGER.debug("Setting brightness of light (%s): %s %s%%",
                              self.host, self.brightness, percent_brightness)
            else:
                _LOGGER.error(
                    "Setting brightness of light (%s) failed: %s %s%%",
                    self.host, self.brightness, percent_brightness)

        if ATTR_COLOR_TEMP in kwargs:
            self._color_temp = kwargs[ATTR_COLOR_TEMP]

            percent_cct = self.translate(self._color_temp, self.max_mireds,
                                         self.min_mireds, CCT_MIN, CCT_MAX)

            if self.light.set_cct(percent_cct) == SUCCESS:
                _LOGGER.debug(
                    "Setting color temperature of light (%s): "
                    "%s mireds, %s%% cct",
                    self.host, self._color_temp, percent_cct)
            else:
                _LOGGER.error(
                    "Setting color temperature of light (%s) failed: "
                    "%s mireds, %s%% cct",
                    self.host, self._color_temp, percent_cct)

        if self.light.on() == SUCCESS:
            self._state = True
        else:
            _LOGGER.error("Turning the light (%s) on failed.", self.host)

    def turn_off(self, **kwargs):
        """Turn the light off."""
        if self.light.off() == SUCCESS:
            self._state = False
        else:
            _LOGGER.error("Turning the light (%s) off failed.", self.host)

    def update(self):
        """Fetch state from the device."""
        from mirobo import DeviceException
        try:
            state = self.light.status()
            _LOGGER.debug("Got state from light (%s): %s", self.host, state)

            self._state = state.is_on
            self._brightness = int(255 * 0.01 * state.bright)
            self._color_temp = self.translate(state.cct, CCT_MIN, CCT_MAX,
                                              self.max_mireds,
                                              self.min_mireds)

        except DeviceException as ex:
            _LOGGER.error(
                "Got exception from light (%s) while fetching the state: "
                "%s", ex, self.host)

    @staticmethod
    def translate(value, left_min, left_max, right_min, right_max):
        """Map a value from left span to right span."""
        left_span = left_max - left_min
        right_span = right_max - right_min
        value_scaled = float(value - left_min) / float(left_span)
        return int(right_min + (value_scaled * right_span))
