import logging

import voluptuous as vol

# Import the device class from the component that you want to support
from homeassistant.components.light import ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, ATTR_RGB_COLOR, SUPPORT_RGB_COLOR, Light, PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv

# Home Assistant depends on 3rd party packages for API specific code.
REQUIREMENTS = ['piglow']

_LOGGER = logging.getLogger(__name__)

SUPPORT_PIGLOW = (SUPPORT_BRIGHTNESS | SUPPORT_RGB_COLOR)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Piglow Light platform."""
    import piglow


    # Add devices
    add_devices([PiglowLight(piglow)])


class PiglowLight(Light):
    """Representation of an Piglow Light."""

    def __init__(self, piglow):
        """Initialize an PiglowLight."""
        self._piglow = piglow
        self._isOn = False
        self._brightness = 255
        self._rgb_color = [255, 255, 255]

    @property
    def name(self):
        """Return the display name of this light."""
        return "piglow"

    @property
    def brightness(self):
        """Brightness of the light (an integer in the range 1-255).

        This method is optional. Removing it indicates to Home Assistant
        that brightness is not supported for this light.
        """
        return self._brightness

    @property
    def rgb_color(self):
        """Read back the color of the light."""
        return self._rgb_color

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_PIGLOW

    @property
    def is_on(self):
        """Return true if light is on."""
        return self._isOn

    def turn_on(self, **kwargs):
        """Instruct the light to turn on.

        You can skip the brightness part if your light does not support
        brightness control.
        """
        self._piglow.clear()
        self._brightness = kwargs.get(ATTR_BRIGHTNESS, 255)
        percentBright = (self._brightness / 255)

        if ATTR_RGB_COLOR in kwargs:
            self._rgb_color = kwargs[ATTR_RGB_COLOR]
            self._piglow.red(int(self._rgb_color[0] * percentBright))
            self._piglow.green(int(self._rgb_color[1] * percentBright))
            self._piglow.blue(int(self._rgb_color[2] * percentBright))
        else:
            self._piglow.all(self._brightness)
        self._piglow.show()
        self._isOn = True;

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        self._piglow.clear()
        self._piglow.show()
        self._isOn = False

    def update(self):
        """Fetch new state data for this light.

        This is the only method that should fetch new data for Home Assistant.
        """