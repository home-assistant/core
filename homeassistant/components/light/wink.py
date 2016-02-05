"""
homeassistant.components.light.wink
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for Wink lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.wink/
"""
import logging

from homeassistant.components.light import (ATTR_BRIGHTNESS, ATTR_COLOR_TEMP)
from homeassistant.components.wink import WinkToggleDevice
from homeassistant.const import CONF_ACCESS_TOKEN

REQUIREMENTS = ['python-wink==0.4.2']

TEMP_MIN = 1900               # Wink minimum temperature
TEMP_MAX = 6500               # Wink maximum temperature
TEMP_MIN_HASS = 154           # home assistant minimum temperature
TEMP_MAX_HASS = 500           # home assistant maximum temperature


def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return Wink lights. """
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


class WinkLight(WinkToggleDevice):
    """ Represents a Wink light. """

    # pylint: disable=too-few-public-methods
    def turn_on(self, **kwargs):
        """ Turns the switch on. """

        temp_kelvin = None

        brightness = kwargs.get(ATTR_BRIGHTNESS)

        if ATTR_COLOR_TEMP in kwargs:
            temp_kelvin = int(((TEMP_MAX - TEMP_MIN) *
                               (kwargs[ATTR_COLOR_TEMP] - TEMP_MIN_HASS) /
                               (TEMP_MAX_HASS - TEMP_MIN_HASS)) + TEMP_MIN)

        if brightness is not None:
            brightness = brightness / 255

        self.wink.set_state(True, brightness, temp_kelvin)

    @property
    def state_attributes(self):
        attr = super().state_attributes

        if self.is_on:
            brightness = self.wink.brightness()
            temp_kelvin = self.wink.color_temperature_kelvin()

            if brightness is not None:
                attr[ATTR_BRIGHTNESS] = int(brightness * 255)
            if temp_kelvin is not None:
                attr[ATTR_COLOR_TEMP] = int(TEMP_MIN_HASS +
                                            (TEMP_MAX_HASS - TEMP_MIN_HASS) *
                                            (temp_kelvin - TEMP_MIN) /
                                            (TEMP_MAX - TEMP_MIN))

        return attr
