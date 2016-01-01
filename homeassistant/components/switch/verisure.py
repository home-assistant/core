"""
homeassistant.components.switch.verisure
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for Verisure Smartplugs.

For more details about this platform, please refer to the documentation at
documentation at https://home-assistant.io/components/verisure/
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
        for value in verisure.SMARTPLUG_STATUS.values()
        if verisure.SHOW_SMARTPLUGS
        ])

    add_devices(switches)


class VerisureSmartplug(SwitchDevice):
    """ Represents a Verisure smartplug. """
    def __init__(self, smartplug_status):
        self._id = smartplug_status.id

    @property
    def name(self):
        """ Get the name (location) of the smartplug. """
        return verisure.SMARTPLUG_STATUS[self._id].location

    @property
    def is_on(self):
        """ Returns True if on """
        plug_status = verisure.SMARTPLUG_STATUS[self._id].status
        return plug_status == 'on'

    def turn_on(self):
        """ Set smartplug status on. """
        verisure.MY_PAGES.smartplug.set(self._id, 'on')
        verisure.MY_PAGES.smartplug.wait_while_updating(self._id, 'on')
        verisure.update_smartplug()

    def turn_off(self):
        """ Set smartplug status off. """
        verisure.MY_PAGES.smartplug.set(self._id, 'off')
        verisure.MY_PAGES.smartplug.wait_while_updating(self._id, 'off')
        verisure.update_smartplug()

    def update(self):
        verisure.update_smartplug()
