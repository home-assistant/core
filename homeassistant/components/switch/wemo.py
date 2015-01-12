""" Support for WeMo switchces. """
import logging

from homeassistant.helpers import ToggleDevice
from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.components.switch import (
    ATTR_TODAY_MWH, ATTR_CURRENT_POWER_MWH)


# pylint: disable=unused-argument
def get_devices(hass, config):
    """ Find and return WeMo switches. """

    pywemo, _ = get_pywemo()

    if pywemo is None:
        return []

    logging.getLogger(__name__).info("Scanning for WeMo devices")
    switches = pywemo.discover_devices()

    # Filter out the switches and wrap in WemoSwitch object
    return [WemoSwitch(switch) for switch in switches
            if isinstance(switch, pywemo.Switch)]


def devices_discovered(hass, config, info):
    """ Called when a device is discovered. """
    _, discovery = get_pywemo()

    if discovery is None:
        return []

    device = discovery.device_from_description(info)

    return [] if device is None else [WemoSwitch(device)]


def get_pywemo():
    """ Tries to import PyWemo. """
    try:
        # pylint: disable=no-name-in-module, import-error
        import homeassistant.external.pywemo.pywemo as pywemo
        import homeassistant.external.pywemo.pywemo.discovery as discovery

        return pywemo, discovery

    except ImportError:
        logging.getLogger(__name__).exception((
            "Failed to import pywemo. "
            "Did you maybe not run `git submodule init` "
            "and `git submodule update`?"))

        return None, None


class WemoSwitch(ToggleDevice):
    """ represents a WeMo switch within home assistant. """
    def __init__(self, wemo):
        self.wemo = wemo

    @property
    def unique_id(self):
        """ Returns the id of this WeMo switch """
        return "{}.{}".format(self.__class__, self.wemo.serialnumber)

    @property
    def name(self):
        """ Returns the name of the switch if any. """
        return self.wemo.name

    @property
    def state_attributes(self):
        """ Returns optional state attributes. """
        if self.wemo.model.startswith('Belkin Insight'):
            cur_info = self.wemo.insight_params

            return {
                ATTR_FRIENDLY_NAME: self.wemo.name,
                ATTR_CURRENT_POWER_MWH: cur_info['currentpower'],
                ATTR_TODAY_MWH: cur_info['todaymw']
            }
        else:
            return {ATTR_FRIENDLY_NAME: self.wemo.name}

    @property
    def is_on(self):
        """ True if switch is on. """
        return self.wemo.get_state(True)

    def turn_on(self, **kwargs):
        """ Turns the switch on. """
        self.wemo.on()

    def turn_off(self):
        """ Turns the switch off. """
        self.wemo.off()
