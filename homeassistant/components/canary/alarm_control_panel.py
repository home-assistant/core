"""
Support for Canary alarm.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.canary/
"""
import logging

from homeassistant.components.alarm_control_panel import AlarmControlPanel
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME, STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED)

from . import DATA_CANARY

DEPENDENCIES = ['canary']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Canary alarms."""
    data = hass.data[DATA_CANARY]
    devices = []

    for location in data.locations:
        devices.append(CanaryAlarm(data, location.location_id))

    add_entities(devices, True)


class CanaryAlarm(AlarmControlPanel):
    """Representation of a Canary alarm control panel."""

    def __init__(self, data, location_id):
        """Initialize a Canary security camera."""
        self._data = data
        self._location_id = location_id

    @property
    def name(self):
        """Return the name of the alarm."""
        location = self._data.get_location(self._location_id)
        return location.name

    @property
    def state(self):
        """Return the state of the device."""
        from canary.api import LOCATION_MODE_AWAY, LOCATION_MODE_HOME, \
            LOCATION_MODE_NIGHT

        location = self._data.get_location(self._location_id)

        if location.is_private:
            return STATE_ALARM_DISARMED

        mode = location.mode
        if mode.name == LOCATION_MODE_AWAY:
            return STATE_ALARM_ARMED_AWAY
        if mode.name == LOCATION_MODE_HOME:
            return STATE_ALARM_ARMED_HOME
        if mode.name == LOCATION_MODE_NIGHT:
            return STATE_ALARM_ARMED_NIGHT
        return None

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        location = self._data.get_location(self._location_id)
        return {
            'private': location.is_private
        }

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        location = self._data.get_location(self._location_id)
        self._data.set_location_mode(self._location_id, location.mode.name,
                                     True)

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        from canary.api import LOCATION_MODE_HOME
        self._data.set_location_mode(self._location_id, LOCATION_MODE_HOME)

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        from canary.api import LOCATION_MODE_AWAY
        self._data.set_location_mode(self._location_id, LOCATION_MODE_AWAY)

    def alarm_arm_night(self, code=None):
        """Send arm night command."""
        from canary.api import LOCATION_MODE_NIGHT
        self._data.set_location_mode(self._location_id, LOCATION_MODE_NIGHT)
