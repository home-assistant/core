""" Support for Hue lights. """
import logging

# pylint: disable=no-name-in-module, import-error
import homeassistant.external.wink.pywink as pywink

from homeassistant.helpers import ToggleDevice
from homeassistant.const import ATTR_FRIENDLY_NAME, CONF_ACCESS_TOKEN


# pylint: disable=unused-argument
def get_devices(hass, config):
    """ Find and return Wink lights. """
    token = config.get(CONF_ACCESS_TOKEN)

    if token is None:
        logging.getLogger(__name__).error(
            "Missing wink access_token - "
            "get one at https://winkbearertoken.appspot.com/")
        return []

    pywink.set_bearer_token(token)

    return get_lights()


# pylint: disable=unused-argument
def devices_discovered(hass, config, info):
    """ Called when a device is discovered. """
    return get_lights()


def get_lights():
    """ Returns the Wink switches. """
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
