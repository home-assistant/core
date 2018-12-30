"""
This component provides HA alarm_control_panel support for Lupusec System.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.lupusec/
"""

from datetime import timedelta

from homeassistant.components.alarm_control_panel import AlarmControlPanel
from homeassistant.components.lupusec import DOMAIN as LUPUSEC_DOMAIN
from homeassistant.components.lupusec import LupusecDevice
from homeassistant.const import (STATE_ALARM_ARMED_AWAY,
                                 STATE_ALARM_ARMED_HOME,
                                 STATE_ALARM_DISARMED,
                                 STATE_ALARM_TRIGGERED)

DEPENDENCIES = ['lupusec']

ICON = 'mdi:security'

SCAN_INTERVAL = timedelta(seconds=2)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up an alarm control panel for a Lupusec device."""
    if discovery_info is None:
        return

    data = hass.data[LUPUSEC_DOMAIN]

    alarm_devices = [LupusecAlarm(data, data.lupusec.get_alarm())]

    add_entities(alarm_devices)


class LupusecAlarm(LupusecDevice, AlarmControlPanel):
    """An alarm_control_panel implementation for Lupusec."""

    @property
    def icon(self):
        """Return the icon."""
        return ICON

    @property
    def state(self):
        """Return the state of the device."""
        if self._device.is_standby:
            state = STATE_ALARM_DISARMED
        elif self._device.is_away:
            state = STATE_ALARM_ARMED_AWAY
        elif self._device.is_home:
            state = STATE_ALARM_ARMED_HOME
        elif self._device.is_alarm_triggered:
            state = STATE_ALARM_TRIGGERED
        else:
            state = None
        return state

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        self._device.set_away()

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        self._device.set_standby()

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        self._device.set_home()
