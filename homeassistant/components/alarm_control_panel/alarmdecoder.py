"""
Support for AlarmDecoder-based alarm control panels (Honeywell/DSC).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.alarmdecoder/
"""
import asyncio
import logging

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.alarmdecoder import (
    DATA_AD, SIGNAL_PANEL_MESSAGE)
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED,
    STATE_ALARM_TRIGGERED)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['alarmdecoder']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up for AlarmDecoder alarm panels."""
    add_devices([AlarmDecoderAlarmPanel()])

    return True


class AlarmDecoderAlarmPanel(alarm.AlarmControlPanel):
    """Representation of an AlarmDecoder-based alarm panel."""

    def __init__(self):
        """Initialize the alarm panel."""
        self._display = ""
        self._name = "Alarm Panel"
        self._state = None

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register callbacks."""
        self.hass.helpers.dispatcher.async_dispatcher_connect(
            SIGNAL_PANEL_MESSAGE, self._message_callback)

    def _message_callback(self, message):
        if message.alarm_sounding or message.fire_alarm:
            if self._state != STATE_ALARM_TRIGGERED:
                self._state = STATE_ALARM_TRIGGERED
                self.schedule_update_ha_state()
        elif message.armed_away:
            if self._state != STATE_ALARM_ARMED_AWAY:
                self._state = STATE_ALARM_ARMED_AWAY
                self.schedule_update_ha_state()
        elif message.armed_home:
            if self._state != STATE_ALARM_ARMED_HOME:
                self._state = STATE_ALARM_ARMED_HOME
                self.schedule_update_ha_state()
        else:
            if self._state != STATE_ALARM_DISARMED:
                self._state = STATE_ALARM_DISARMED
                self.schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def code_format(self):
        """Return the regex for code format or None if no code is required."""
        return '^\\d{4,6}$'

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        if code:
            _LOGGER.debug("alarm_disarm: sending %s1", str(code))
            self.hass.data[DATA_AD].send("{!s}1".format(code))

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        if code:
            _LOGGER.debug("alarm_arm_away: sending %s2", str(code))
            self.hass.data[DATA_AD].send("{!s}2".format(code))

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        if code:
            _LOGGER.debug("alarm_arm_home: sending %s3", str(code))
            self.hass.data[DATA_AD].send("{!s}3".format(code))
