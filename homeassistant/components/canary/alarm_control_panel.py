"""Support for Canary alarm."""
import logging

from canary.api import LOCATION_MODE_AWAY, LOCATION_MODE_HOME, LOCATION_MODE_NIGHT

from homeassistant.components.alarm_control_panel import AlarmControlPanelEntity
from homeassistant.components.alarm_control_panel.const import (
    SUPPORT_ALARM_ARM_AWAY,
    SUPPORT_ALARM_ARM_HOME,
    SUPPORT_ALARM_ARM_NIGHT,
)
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
)

from . import DATA_CANARY

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Canary alarms."""
    data = hass.data[DATA_CANARY]
    devices = [CanaryAlarm(data, location.location_id) for location in data.locations]

    add_entities(devices, True)


class CanaryAlarm(AlarmControlPanelEntity):
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
    def unique_id(self):
        """Return the unique ID of the alarm."""
        return str(self._location_id)

    @property
    def state(self):
        """Return the state of the device."""
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
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_ALARM_ARM_HOME | SUPPORT_ALARM_ARM_AWAY | SUPPORT_ALARM_ARM_NIGHT

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        location = self._data.get_location(self._location_id)
        return {"private": location.is_private}

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        location = self._data.get_location(self._location_id)
        self._data.set_location_mode(self._location_id, location.mode.name, True)

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        self._data.set_location_mode(self._location_id, LOCATION_MODE_HOME)

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        self._data.set_location_mode(self._location_id, LOCATION_MODE_AWAY)

    def alarm_arm_night(self, code=None):
        """Send arm night command."""
        self._data.set_location_mode(self._location_id, LOCATION_MODE_NIGHT)

    def update(self):
        """Get the latest state of the sensor."""
        self._data.update()
