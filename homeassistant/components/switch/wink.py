""" Support for WeMo switchces. """
import logging

import homeassistant as ha
from homeassistant.helpers import ToggleDevice
from homeassistant.const import ATTR_FRIENDLY_NAME


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
    token = config["access_token"]
    pywink.set_bearer_token(token)

    switches = pywink.get_switches()



    # Filter out the switches and wrap in WemoSwitch object
    return [WinkSwitch(switch) for switch in switches]


class WinkSwitch(ToggleDevice):
    """ represents a WeMo switch within home assistant. """

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
