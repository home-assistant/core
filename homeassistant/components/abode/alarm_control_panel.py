"""Support for Abode Security System alarm control panels."""
import logging

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.const import (
    ATTR_ATTRIBUTION, STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED)

from . import ATTRIBUTION, DOMAIN as ABODE_DOMAIN, AbodeDevice

DEPENDENCIES = ['abode']

_LOGGER = logging.getLogger(__name__)

ICON = 'mdi:security'


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up an alarm control panel for an Abode device."""
    data = hass.data[ABODE_DOMAIN]

    alarm_devices = [AbodeAlarm(data, data.abode.get_alarm(), data.name)]

    data.devices.extend(alarm_devices)

    add_entities(alarm_devices)


class AbodeAlarm(AbodeDevice, alarm.AlarmControlPanel):
    """An alarm_control_panel implementation for Abode."""

    def __init__(self, data, device, name):
        """Initialize the alarm control panel."""
        super().__init__(data, device)
        self._name = name

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
    def name(self):
        """Return the name of the alarm."""
        return self._name or super().name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
            'device_id': self._device.device_id,
            'battery_backup': self._device.battery,
            'cellular_backup': self._device.is_cellular,
        }
