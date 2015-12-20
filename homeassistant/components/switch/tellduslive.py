"""
homeassistant.components.switch.tellduslive
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for Tellstick switches using Tellstick Net and the Telldus Live online service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.tellduslive/
"""
import logging

from homeassistant.const import STATE_UNKNOWN
from homeassistant.components import tellduslive
from homeassistant.helpers.entity import ToggleEntity

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = ['tellduslive']

def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Find and return Tellstick switches. """
    switches = tellduslive.NETWORK.get_switches()
    # fixme: metadata groups etc
    add_devices([TelldusLiveSwitch(switch["name"], 
                                   switch["id"]) \
                 for switch in switches])

class TelldusLiveSwitch(ToggleEntity):
    """ Represents a Tellstick switch. """
    
    def __init__(self, name, switch_id):
        self._name = name
        self._id = switch_id

    @property
    def should_poll(self):
        """ Tells Home Assistant not to poll this entity. """
        return True

    @property
    def name(self):
        """ Returns the name of the switch if any. """
        return self._name

    @property
    def state(self):
        """ Returns the state. """
        return STATE_UNKNOWN

    #@property
    #def state_attributes(self):
    #    """ Returns optional state attributes. """
    #    pass

    #@property
    #def is_on(self):
    #    """ True if switch is on. """
    #    pass

    def turn_on(self, **kwargs):
        """ Turns the switch on. """
        pass

    def turn_off(self, **kwargs):
        """ Turns the switch off. """
        pass
