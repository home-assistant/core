"""
homeassistant.components.switch.edimax
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Support for Edimax switches.
"""
import logging

from homeassistant.components.switch import SwitchDevice
from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return Edimax Smart Plugs. """
    try:
        # pylint: disable=no-name-in-module, import-error
        from homeassistant.external.pyedimax.smartplug import SmartPlug
    except ImportError:
        logging.getLogger(__name__).exception((
            "Failed to import pyedimax. "
            "Did you maybe not run `git submodule init` "
            "and `git submodule update`?"))

        return

    host = config.get(CONF_HOST)
    auth = (config.get(CONF_USERNAME, 'admin'),
            config.get(CONF_PASSWORD, '1234'))

    if not host:
        logging.getLogger(__name__).error(
            'Missing config variable %s', CONF_HOST)
        return False

    add_devices_callback([SmartPlugSwitch(SmartPlug(host, auth))])


class SmartPlugSwitch(SwitchDevice):
    """ Represents a Edimax Smart Plug switch within Home Assistant. """
    def __init__(self, smartplug):
        self.smartplug = smartplug

    @property
    def name(self):
        """ Returns the name of the Smart Plug, if any. """
        #TODO: dynamically get name from device using requests
        return 'Edimax Smart Plug'

    @property
    def current_power_mwh(self):
        """ Current power usage in mwh. """
        try:
            return float(self.smartplug.now_power) / 1000000.0
        except ValueError:
            return None

    @property
    def today_power_mw(self):
        """ Today total power usage in mw. """
        try:
            return float(self.smartplug.now_energy_day) / 1000.0
        except ValueError:
            return None

    @property
    def is_on(self):
        """ True if switch is on. """
        return self.smartplug.state == 'ON'

    def turn_on(self, **kwargs):
        """ Turns the switch on. """
        self.smartplug.state = 'ON'

    def turn_off(self):
        """ Turns the switch off. """
        self.smartplug.state = 'OFF'
