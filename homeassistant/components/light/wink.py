"""
homeassistant.components.light.wink
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for Wink lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.wink/
"""
import logging

from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.components.wink import WinkToggleDevice
from homeassistant.const import CONF_ACCESS_TOKEN

REQUIREMENTS = ['python-wink==0.4.2']


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
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        if brightness is not None:
            self.wink.set_state(True, brightness=brightness / 255)

        else:
            self.wink.set_state(True)

    @property
    def state_attributes(self):
        attr = super().state_attributes

        if self.is_on:
            brightness = self.wink.brightness()

            if brightness is not None:
                attr[ATTR_BRIGHTNESS] = int(brightness * 255)

        return attr
