"""
This component provides HA alarm_control_panel support for Abode System.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.abode/
"""
import logging

from homeassistant.components.abode import (
    AbodeDevice, ABODE_CONTROLLER, DEFAULT_NAME)
from homeassistant.const import (STATE_ALARM_ARMED_AWAY,
                                 STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED)
import homeassistant.components.alarm_control_panel as alarm

DEPENDENCIES = ['abode']

_LOGGER = logging.getLogger(__name__)

ICON = 'mdi:security'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up a sensor for an Abode device."""

    add_devices([AbodeAlarm(hass, ABODE_CONTROLLER, ABODE_CONTROLLER.get_alarm())])


class AbodeAlarm(AbodeDevice, alarm.AlarmControlPanel):
    """An alarm_control_panel implementation for Abode."""

    def __init__(self, hass, controller, device):
        """Initialize the alarm control panel."""
        AbodeDevice.__init__(self, hass, controller, device)
        self._device = device
        self._name = "{0}".format(DEFAULT_NAME)

    @property
    def icon(self):
        """Return icon."""
        return ICON

    @property
    def state(self):
        """Return the state of the device."""
        if self._device.mode == "standby":
            state = STATE_ALARM_DISARMED
        elif self._device.mode == "away":
            state = STATE_ALARM_ARMED_AWAY
        elif self._device.mode == "home":
            state = STATE_ALARM_ARMED_HOME
        else:
            state = None
        return state

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        self._device.set_standby()

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        self._device.set_home()

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        self._device.set_away()

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        self._attrs = super().device_state_attributes
        self._attrs['battery_backup'] = self._device.battery
        self._attrs['cellular_backup'] = self._device.is_cellular

        return self._attrs
