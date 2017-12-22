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
        self._ac_power = None
        self._backlight_on = None
        self._battery_low = None
        self._check_zone = None
        self._chime = None
        self._entry_delay_off = None
        self._programming_mode = None
        self._ready = None
        self._zone_bypassed = None

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register callbacks."""
        self.hass.helpers.dispatcher.async_dispatcher_connect(
            SIGNAL_PANEL_MESSAGE, self._message_callback)

    def _message_callback(self, message):
        do_update = False

        if message.alarm_sounding or message.fire_alarm:
            if self._state != STATE_ALARM_TRIGGERED:
                self._state = STATE_ALARM_TRIGGERED
                do_update = True
        elif message.armed_away:
            if self._state != STATE_ALARM_ARMED_AWAY:
                self._state = STATE_ALARM_ARMED_AWAY
                do_update = True
        elif message.armed_home:
            if self._state != STATE_ALARM_ARMED_HOME:
                self._state = STATE_ALARM_ARMED_HOME
                do_update = True
        else:
            if self._state != STATE_ALARM_DISARMED:
                self._state = STATE_ALARM_DISARMED
                do_update = True

        if self._ac_power != message.ac_power:
            self._ac_power = message.ac_power
            do_update = True

        if self._backlight_on != message.backlight_on:
            self._backlight_on = message.backlight_on
            do_update = True

        if self._battery_low != message.battery_low:
            self._battery_low = message.battery_low
            do_update = True

        if self._check_zone != message.check_zone:
            self._check_zone = message.check_zone
            do_update = True

        if self._chime != message.chime_on:
            self._chime = message.chime_on
            do_update = True

        if self._entry_delay_off != message.entry_delay_off:
            self._entry_delay_off = message.entry_delay_off
            do_update = True

        if self._programming_mode != message.programming_mode:
            self._programming_mode = message.programming_mode
            do_update = True

        if self._ready != message.ready:
            self._ready = message.ready
            do_update = True

        if self._zone_bypassed != message.zone_bypassed:
            self._zone_bypassed = message.zone_bypassed
            do_update = True

        if do_update is True:
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

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            'ac_power': self._ac_power,
            'backlight_on': self._backlight_on,
            'battery_low': self._battery_low,
            'check_zone': self._check_zone,
            'chime': self._chime,
            'entry_delay_off': self._entry_delay_off,
            'programming_mode': self._programming_mode,
            'ready': self._ready,
            'zone_bypassed': self._zone_bypassed
        }

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
