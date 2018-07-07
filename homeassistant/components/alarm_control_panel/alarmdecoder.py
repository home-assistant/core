"""
Support for AlarmDecoder-based alarm control panels (Honeywell/DSC).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.alarmdecoder/
"""
import asyncio
import logging

import voluptuous as vol

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.alarmdecoder import DATA_AD, SIGNAL_PANEL_MESSAGE
from homeassistant.const import (
    ATTR_CODE, STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME,
    STATE_ALARM_DISARMED, STATE_ALARM_TRIGGERED)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['alarmdecoder']

SERVICE_ALARM_TOGGLE_CHIME = 'alarmdecoder_alarm_toggle_chime'
ALARM_TOGGLE_CHIME_SCHEMA = vol.Schema({
    vol.Required(ATTR_CODE): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up for AlarmDecoder alarm panels."""
    device = AlarmDecoderAlarmPanel()
    add_devices([device])

    def alarm_toggle_chime_handler(service):
        """Register toggle chime handler."""
        code = service.data.get(ATTR_CODE)
        device.alarm_toggle_chime(code)

    hass.services.register(
        alarm.DOMAIN, SERVICE_ALARM_TOGGLE_CHIME, alarm_toggle_chime_handler,
        schema=ALARM_TOGGLE_CHIME_SCHEMA)


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
        """Handle received messages."""
        if message.alarm_sounding or message.fire_alarm:
            self._state = STATE_ALARM_TRIGGERED
        elif message.armed_away:
            self._state = STATE_ALARM_ARMED_AWAY
        elif message.armed_home:
            self._state = STATE_ALARM_ARMED_HOME
        else:
            self._state = STATE_ALARM_DISARMED

        self._ac_power = message.ac_power
        self._backlight_on = message.backlight_on
        self._battery_low = message.battery_low
        self._check_zone = message.check_zone
        self._chime = message.chime_on
        self._entry_delay_off = message.entry_delay_off
        self._programming_mode = message.programming_mode
        self._ready = message.ready
        self._zone_bypassed = message.zone_bypassed

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
        """Return one or more digits/characters."""
        return 'Number'

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
            'zone_bypassed': self._zone_bypassed,
        }

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        if code:
            self.hass.data[DATA_AD].send("{!s}1".format(code))

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        if code:
            self.hass.data[DATA_AD].send("{!s}2".format(code))

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        if code:
            self.hass.data[DATA_AD].send("{!s}3".format(code))

    def alarm_toggle_chime(self, code=None):
        """Send toggle chime command."""
        if code:
            self.hass.data[DATA_AD].send("{!s}9".format(code))
