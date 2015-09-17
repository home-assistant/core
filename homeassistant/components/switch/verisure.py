"""
homeassistant.components.switch.verisure
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for Verisure Smartplugs.
"""
import logging

import homeassistant.components.verisure as verisure
from homeassistant.components.switch import SwitchDevice

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the Verisure platform. """

    if not verisure.MY_PAGES:
        _LOGGER.error('A connection has not been made to Verisure mypages.')
        return False

    switches = []

    switches.extend([
        VerisureSmartplug(value)
        for value in verisure.get_smartplug_status().values()
        if verisure.SHOW_SMARTPLUGS
        ])

    add_devices(switches)


class VerisureSmartplug(SwitchDevice):
    """ Represents a Verisure smartplug. """
    def __init__(self, smartplug_status):
        self._id = smartplug_status.id
        self.status_on = verisure.MY_PAGES.SMARTPLUG_ON
        self.status_off = verisure.MY_PAGES.SMARTPLUG_OFF

    @property
    def name(self):
        """ Get the name (location) of the smartplug. """
        return verisure.get_smartplug_status()[self._id].location

    @property
    def is_on(self):
        """ Returns True if on """
        plug_status = verisure.get_smartplug_status()[self._id].status
        return plug_status == self.status_on

    def turn_on(self):
        """ Set smartplug status on. """
        verisure.MY_PAGES.set_smartplug_status(
            self._id,
            self.status_on)

    def turn_off(self):
        """ Set smartplug status off. """
        verisure.MY_PAGES.set_smartplug_status(
            self._id,
            self.status_off)

    def update(self):
        verisure.update()
