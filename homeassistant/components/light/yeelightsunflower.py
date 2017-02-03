"""
Support for Yeelight Sunflower colour bulbs (not Yeelight Blue or WiFi).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.yeelight-sunflower/ (maybe one day)
"""
import logging
import voluptuous as vol

from homeassistant.components.light import (Light,
                                            ATTR_RGB_COLOR,
                                            ATTR_BRIGHTNESS,
                                            SUPPORT_BRIGHTNESS,
                                            SUPPORT_RGB_COLOR,
                                            PLATFORM_SCHEMA)
from homeassistant.const import CONF_HOST
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['yeelightsunflower>=0.0.1']
SUPPORT_YEELIGHT_SUNFLOWER = (SUPPORT_BRIGHTNESS | SUPPORT_RGB_COLOR)

_LOGGER = logging.getLogger(__name__)

# Validate the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Yeelight Sunflower Light platform."""
    import yeelightsunflower

    # Assign configuration variables. The configuration check takes care they are
    # present.
    host = config.get(CONF_HOST)

    # Setup connection with Yeelight Sunflower hub
    hub = yeelightsunflower.Hub(host)

    # Verify that hub is responsive
    if not hub.check():
        _LOGGER.error('Could not connect to Yeelight Sunflower hub')
        return False

    # Add devices
    add_devices(SunflowerBulb(light) for light in hub.get_lights())


class SunflowerBulb(Light):
    """Representation of a Yeelight Sunflower Light."""

    def __init__(self, light):
        """Initialize a Yeelight Sunflower bulb."""
        self._light = light

    @property
    def unique_id(self):
        """Return the ID of this light."""
        return "{}.{}".format(self.__class__, self._light.id)

    @property
    def name(self):
        """Return the display name of this light."""
        return "sunflower_{}".format(self._light.id)

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._light.is_on()

    @property
    def brightness(self):
        """Brightness of the light (an integer in the range 1-255).
        """
        return self._light.brightness

    @property
    def rgb_color(self):
        """Return the color property."""
        return self._light.rgb_color

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_YEELIGHT_SUNFLOWER

    def turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        # self._light.brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
        self._light.turn_on()

        if ATTR_RGB_COLOR in kwargs:
            rgb = kwargs[ATTR_RGB_COLOR]
            self._light.set_rgb_color(rgb[0], rgb[1], rgb[2])
            # self._rgb = [rgb[0], rgb[1], rgb[2]]

        if ATTR_BRIGHTNESS in kwargs:
            bright = int(kwargs[ATTR_BRIGHTNESS] * 100 / 255)
            self._light.set_brightness(bright)
            # self._bright = kwargs[ATTR_BRIGHTNESS]

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        self._light.turn_off()

    def update(self):
        """Fetch new state data for this light."""
        self._light.update()
