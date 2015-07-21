"""
homeassistant.components.switch.edimax
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Support for Edimax switches.
"""
import logging

from homeassistant.components.switch import SwitchDevice


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


    add_devices_callback([
        SmartPlugSwitch(SmartPlug(
            host = config.get('host'),
            auth=(
                config.get('user', 'admin'),
                config.get('password', '1234'))))
    ])


class SmartPlugSwitch(SwitchDevice):
    """ Represents a Edimax Smart Plug switch within Home Assistant. """
    def __init__(self, smartplug):
        self.smartplug = smartplug

    @property
    def is_on(self):
        """ True if switch is on. """
        return self.smartplug.get_state()

    def turn_on(self, **kwargs):
        """ Turns the switch on. """
        self.smartplug.state = 'ON'

    def turn_off(self):
        """ Turns the switch off. """
        self.smartplug.state = 'OFF'