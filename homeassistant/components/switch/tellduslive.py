"""
homeassistant.components.switch.tellduslive
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for Tellstick switches using Tellstick Net and
the Telldus Live online service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.tellduslive/

"""
import logging

from homeassistant.const import (STATE_ON, STATE_OFF, STATE_UNKNOWN)
from homeassistant.components import tellduslive
from homeassistant.helpers.entity import ToggleEntity

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Find and return Tellstick switches. """
    if discovery_info is None:
        return
    switches = tellduslive.NETWORK.get_switches()
    add_devices([TelldusLiveSwitch(switch["name"],
                                   switch["id"])
                 for switch in switches if switch["type"] == "device"])


class TelldusLiveSwitch(ToggleEntity):
    """ Represents a Tellstick switch. """

    def __init__(self, name, switch_id):
        self._name = name
        self._id = switch_id
        self._state = STATE_UNKNOWN
        self.update()

    @property
    def should_poll(self):
        """ Tells Home Assistant to poll this entity. """
        return False

    @property
    def name(self):
        """ Returns the name of the switch if any. """
        return self._name

    def update(self):
        from tellive.live import const
        state = tellduslive.NETWORK.get_switch_state(self._id)
        if state == const.TELLSTICK_TURNON:
            self._state = STATE_ON
        elif state == const.TELLSTICK_TURNOFF:
            self._state = STATE_OFF
        else:
            self._state = STATE_UNKNOWN

    @property
    def is_on(self):
        """ True if switch is on. """
        return self._state == STATE_ON

    def turn_on(self, **kwargs):
        """ Turns the switch on. """
        if tellduslive.NETWORK.turn_switch_on(self._id):
            self._state = STATE_ON
            self.update_ha_state()

    def turn_off(self, **kwargs):
        """ Turns the switch off. """
        if tellduslive.NETWORK.turn_switch_off(self._id):
            self._state = STATE_OFF
            self.update_ha_state()
