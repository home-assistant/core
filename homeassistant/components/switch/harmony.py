"""
Support for Harmony activities represented as a switch.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/harmony/
"""

from homeassistant.components.switch import ToggleEntity
from homeassistant.const import STATE_OFF, STATE_ON
import homeassistant.components.harmony as harmony
import pyharmony
import logging

DEPENDENCIES = ['harmony']
_LOGGER = logging.getLogger(__name__)



def setup_platform(hass, config, add_devices_callback, configData, discovery_info=None):
    for hub in harmony.HARMONY:
        for activity in harmony.HARMONY[hub]['activities']:
            add_devices_callback(
                [HarmonySwitch(harmony.HARMONY[hub]['device'], activity, harmony.HARMONY[hub]['activities'][activity])])
    return True


class HarmonySwitch(harmony.HarmonyDevice, ToggleEntity):
    """Switch used to start an activity via a Harmony device"""

    def __init__(self, harmony_device, activity_name, activity_id):
        self._harmony_device = harmony_device
        self._name = 'harmony_' + self._harmony_device.name + '_' + activity_name
        self._activityID = activity_id
        self._activityName = activity_name


    @property
    def activityID(self):
        return self._activityID

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._harmony_device.get_status() == self._activityName:
            return STATE_ON
        else:
            return STATE_OFF

    @property
    def state_attributes(self):
        """Overwrite inherited attributes"""
        return {'activity_id': self._activityID,
                'activity_name': self._activityName}

    def turn_on(self):
        """Turn the switch on."""
        config = self._harmony_device.config
        pyharmony.ha_start_activity(config['email'], config['password'], config['ip'], config['port'], self._activityID)
        self.turn_off()


    def turn_off(self):
        """Turn the switch off."""
        self._state = False
