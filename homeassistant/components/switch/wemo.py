""" Support for WeMo switchces. """
import logging

import homeassistant as ha
from homeassistant.components import ToggleDevice, ATTR_FRIENDLY_NAME


# pylint: disable=unused-argument
def get_switches(hass, config):
    """ Find and return WeMo switches. """

    try:
        # Pylint does not play nice if not every folders has an __init__.py
        # pylint: disable=no-name-in-module, import-error
        import homeassistant.external.pywemo.pywemo as pywemo
    except ImportError:
        logging.getLogger(__name__).exception((
            "Failed to import pywemo. "
            "Did you maybe not run `git submodule init` "
            "and `git submodule update`?"))

        return []

    if ha.CONF_HOSTS in config:
        switches = (pywemo.device_from_host(host) for host
                    in config[ha.CONF_HOSTS].split(","))

    else:
        logging.getLogger(__name__).info("Scanning for WeMo devices")
        switches = pywemo.discover_devices()

    # Filter out the switches and wrap in WemoSwitch object
    return [WemoSwitch(switch) for switch in switches
            if isinstance(switch, pywemo.Switch)]


class WemoSwitch(ToggleDevice):
    """ represents a WeMo switch within home assistant. """
    def __init__(self, wemo):
        self.wemo = wemo
        self.state_attr = {ATTR_FRIENDLY_NAME: wemo.name}

    def get_name(self):
        """ Returns the name of the switch if any. """
        return self.wemo.name

    def turn_on(self, **kwargs):
        """ Turns the switch on. """
        self.wemo.on()

    def turn_off(self):
        """ Turns the switch off. """
        self.wemo.off()

    def is_on(self):
        """ True if switch is on. """
        return self.wemo.get_state(True)

    def get_state_attributes(self):
        """ Returns optional state attributes. """
        return self.state_attr
