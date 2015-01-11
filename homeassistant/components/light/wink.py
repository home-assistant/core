""" Support for Hue lights. """
import logging

import homeassistant.external.wink.pywink as pywink

from homeassistant.helpers import ToggleDevice
from homeassistant.const import ATTR_FRIENDLY_NAME


# pylint: disable=unused-argument
def get_devices(hass, config):
    """ Find and return Wink lights. """
    token = config.get('access_token')

    if token is None:
        logging.getLogger(__name__).error(
            "Missing wink access_token - "
            "get one at https://winkbearertoken.appspot.com/")
        return False

    pywink.set_bearer_token(token)

    return [WinkLight(light) for light in pywink.get_bulbs()]


class WinkLight(ToggleDevice):
    """ Represents a Wink light """

    def __init__(self, wink):
        self.wink = wink
        self.state_attr = {ATTR_FRIENDLY_NAME: wink.name()}

    def get_name(self):
        """ Returns the name of the light if any. """
        return self.wink.name()

    def turn_on(self, **kwargs):
        """ Turns the light on. """
        self.wink.setState(True)

    def turn_off(self):
        """ Turns the light off. """
        self.wink.setState(False)

    def is_on(self):
        """ True if light is on. """
        return self.wink.state()

    def get_state_attributes(self):
        """ Returns optional state attributes. """
        return self.state_attr
