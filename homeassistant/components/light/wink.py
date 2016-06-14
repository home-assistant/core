"""
Support for Wink lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.wink/
"""
import logging

from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, \
    Light, ATTR_RGB_COLOR
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.util import color as color_util
from homeassistant.util.color import \
    color_temperature_mired_to_kelvin as mired_to_kelvin

REQUIREMENTS = ['python-wink==0.7.6']


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """Setup Wink lights."""
    import pywink

    token = config.get(CONF_ACCESS_TOKEN)

    if not pywink.is_token_set() and token is None:
        logging.getLogger(__name__).error(
            "Missing wink access_token - "
            "get one at https://winkbearertoken.appspot.com/")
        return

    elif token is not None:
        pywink.set_bearer_token(token)

    add_devices_callback(
        WinkLight(light) for light in pywink.get_bulbs())


class WinkLight(Light):
    """Representation of a Wink light."""

    def __init__(self, wink):
        """
        Initialize the light.

        :type wink: pywink.devices.standard.bulb.WinkBulb
        """
        self.wink = wink

    @property
    def unique_id(self):
        """Return the ID of this Wink light."""
        return "{}.{}".format(self.__class__, self.wink.device_id())

    @property
    def name(self):
        """Return the name of the light if any."""
        return self.wink.name()

    @property
    def is_on(self):
        """Return true if light is on."""
        return self.wink.state()

    @property
    def brightness(self):
        """Return the brightness of the light."""
        return int(self.wink.brightness() * 255)

    @property
    def available(self):
        """True if connection == True."""
        return self.wink.available

    @property
    def xy_color(self):
        """Current bulb color in CIE 1931 (XY) color space."""
        if not self.wink.supports_xy_color():
            return None
        return self.wink.color_xy()

    @property
    def color_temp(self):
        """Current bulb color in degrees Kelvin."""
        if not self.wink.supports_temperature():
            return None
        return color_util.color_temperature_kelvin_to_mired(
            self.wink.color_temperature_kelvin())

    # pylint: disable=too-few-public-methods
    def turn_on(self, **kwargs):
        """Turn the switch on."""
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        rgb_color = kwargs.get(ATTR_RGB_COLOR)
        color_temp_mired = kwargs.get(ATTR_COLOR_TEMP)

        state_kwargs = {
        }

        if rgb_color:
            xyb = color_util.color_RGB_to_xy(*rgb_color)
            state_kwargs['color_xy'] = xyb[0], xyb[1]
            state_kwargs['brightness'] = xyb[2]

        if color_temp_mired:
            state_kwargs['color_kelvin'] = mired_to_kelvin(color_temp_mired)

        if brightness:
            state_kwargs['brightness'] = brightness / 255.0

        self.wink.set_state(True, **state_kwargs)

    def turn_off(self):
        """Turn the switch off."""
        self.wink.set_state(False)

    def update(self):
        """Update state of the light."""
        self.wink.update_state(require_desired_state_fulfilled=True)
