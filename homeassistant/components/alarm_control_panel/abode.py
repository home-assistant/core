"""
This component provides HA alarm_control_panel support for Abode System.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.abode/
"""
import logging

from homeassistant.components.abode import (DATA_ABODE, DEFAULT_NAME)
from homeassistant.const import (STATE_UNKNOWN)
import homeassistant.components.alarm_control_panel as alarm

DEPENDENCIES = ['abode']

_LOGGER = logging.getLogger(__name__)

ALARM_STATE_HOME = 'home'
ALARM_STATE_STANDBY = 'standby'
ALARM_STATE_AWAY = 'away'
ICON = 'mdi:security'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up a sensor for an Abode device."""
    data = hass.data.get(DATA_ABODE)

    add_devices([AbodeAlarm(hass, data, data.abode.get_alarm())])


class AbodeAlarm(alarm.AlarmControlPanel):
    """An alarm_control_panel implementation for Abode."""

    def __init__(self, hass, data, device):
        """Initialize the alarm control panel."""
        super(AbodeAlarm, self).__init__()
        self._device = device
        self._name = "{0}".format(DEFAULT_NAME)

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return icon."""
        return ICON

    @property
    def state(self):
        """Return the state of the device."""
        status = self._device.mode

        if status in [ALARM_STATE_STANDBY, ALARM_STATE_HOME, ALARM_STATE_AWAY]:
            return status

        return STATE_UNKNOWN

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        self._device.set_mode(mode=ALARM_STATE_STANDBY)
        self.schedule_update_ha_state()

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        self._device.set_mode(mode=ALARM_STATE_HOME)
        self.schedule_update_ha_state()

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        self._device.set_mode(mode=ALARM_STATE_AWAY)
        self.schedule_update_ha_state()

    def update(self):
        """Update the device state."""
        self._device.refresh()
