""" Support for Hue lights. """
import logging

from datetime import timedelta

import homeassistant.util as util
from homeassistant.helpers import ToggleDevice
from homeassistant.const import ATTR_FRIENDLY_NAME, CONF_PLATFORM
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_HUE, ATTR_SATURATION, ATTR_KELVIN)


MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(seconds=1)

# pylint: disable=unused-argument
def get_devices(hass, config):
    """ Find and return WeMo switches. """

    try:
        # Pylint does not play nice if not every folders has an __init__.py
        # pylint: disable=no-name-in-module, import-error
        import homeassistant.components.hubs.pywink.pywink as pywink
    except ImportError:
        logging.getLogger(__name__).exception((
            "Failed to import pywink. "
            "Did you maybe not run `git submodule init` "
            "and `git submodule update`?"))

        return []
    token = config["bearer_token"]
    pywink.set_bearer_token(token)

    switches = pywink.get_bulbs()



    # Filter out the switches and wrap in WemoSwitch object
    return [WinkLight(switch) for switch in switches]



class WinkLight(ToggleDevice):
    """
    Represents a Lifx light
    http://lifx.com

     """

    def __init__(self, wink):
        self.wink = wink
        self.state_attr = {ATTR_FRIENDLY_NAME: wink.name()}

    def get_name(self):
        """ Returns the name of the switch if any. """
        return self.wink.name()

    def turn_on(self, **kwargs):
        """ Turns the switch on. """
        self.wink.setState(True)

    def turn_off(self):
        """ Turns the switch off. """
        self.wink.setState(False)

    def is_on(self):
        """ True if switch is on. """
        return self.wink.state()

    def get_state_attributes(self):
        """ Returns optional state attributes. """
        return self.state_attr

