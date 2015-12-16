"""
homeassistant.components.switch.tellduslive
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for Tellstick switches using Tellstick Net and the Telldus Live online service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.tellduslive/
"""
import logging

from homeassistant.const import (EVENT_HOMEASSISTANT_STOP,
                                 ATTR_FRIENDLY_NAME)
from homeassistant.helpers.entity import ToggleEntity

SIGNAL_REPETITIONS = 1
REQUIREMENTS = ['tellive-py==0.5.2']
_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices_callback, discovery_info=None):
    """ Find and return Tellstick switches. """
    pass

class TellstickSwitchDevice(ToggleEntity):
    """ Represents a Tellstick switch. """
    
    def __init__(self, tellstick_device, signal_repetitions):
        pass

    @property
    def should_poll(self):
        """ Tells Home Assistant not to poll this entity. """
        return False

    @property
    def name(self):
        """ Returns the name of the switch if any. """
        return self.tellstick_device.name

    @property
    def state_attributes(self):
        """ Returns optional state attributes. """
        return self.state_attr

    @property
    def is_on(self):
        """ True if switch is on. """
        pass

    def turn_on(self, **kwargs):
        """ Turns the switch on. """
        self.update_ha_state()

    def turn_off(self, **kwargs):
        """ Turns the switch off. """
        self.update_ha_state()
