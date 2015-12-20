"""
homeassistant.components.switch.tellduslive
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for Tellstick switches using Tellstick Net and the Telldus Live online service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.tellduslive/

"""
import logging

from homeassistant.const import (STATE_ON, STATE_OFF, STATE_UNKNOWN)
from homeassistant.components import tellduslive
from homeassistant.helpers.entity import ToggleEntity

from tellcore.constants import (
    TELLSTICK_TURNON, TELLSTICK_TURNOFF, TELLSTICK_TOGGLE)

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = ['tellduslive']

def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Find and return Tellstick switches. """
    switches = tellduslive.NETWORK.get_switches()
    # fixme: metadata groups etc
    STATES = {0:                 STATE_UNKNOWN,
              TELLSTICK_TURNON:  STATE_ON,
              TELLSTICK_TURNOFF: STATE_OFF}
    add_devices([TelldusLiveSwitch(switch["name"], 
                                   switch["id"],
                                   STATES[switch["state"]])
                 for switch in switches])

class TelldusLiveSwitch(ToggleEntity):
    """ Represents a Tellstick switch. """
    
    def __init__(self, name, switch_id, state):
        self._name = name
        self._id = switch_id
        self._state = state

    @property
    def should_poll(self):
        """ Tells Home Assistant to poll this entity. """
        return True

    @property
    def name(self):
        """ Returns the name of the switch if any. """
        return self._name

    @property
    def state(self):
        """ Returns the state. """
        return self._state

    #@property
    #def state_attributes(self):
    #    """ Returns optional state attributes. """
    #    pass

    @property
    def is_on(self):
        """ True if switch is on. """
        return self.state() == STATE_ON

    def turn_on(self, **kwargs):
        """ Turns the switch on. """
        response = tellduslive.NETWORK.request("device/turnOn", {"id": self._id})
        if response["status"] == "success":
            self._state = STATE_ON

    def turn_off(self, **kwargs):
        """ Turns the switch off. """
        response = tellduslive.NETWORK.request("device/turnOff", {"id": self._id})
        if response["status"] == "success":
            self._state = STATE_OFF

