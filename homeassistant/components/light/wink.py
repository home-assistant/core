""" Support for Hue lights. """
import logging

# pylint: disable=no-name-in-module, import-error
import homeassistant.external.wink.pywink as pywink

from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.components.wink import WinkToggleDevice
from homeassistant.const import CONF_ACCESS_TOKEN


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


class WinkLight(WinkToggleDevice):
    """ Represents a Wink light """

    # pylint: disable=too-few-public-methods
    def turn_on(self, **kwargs):
        """ Turns the switch on. """
        brightness = kwargs.get(ATTR_BRIGHTNESS)

        if brightness is not None:
            self.wink.setState(True, brightness / 255)

        else:
            self.wink.setState(True)

    @property
    def state_attributes(self):
        attr = super().state_attributes

        if self.is_on:
            brightness = self.wink.brightness()

            if brightness is not None:
                attr[ATTR_BRIGHTNESS] = int(brightness * 255)

        return attr
