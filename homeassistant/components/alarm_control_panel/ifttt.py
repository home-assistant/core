"""
Interfaces with alarm control panels that have to be controlled through IFTTT.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.ifttt_securitysystem/
"""
import logging
import voluptuous as vol

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.alarm_control_panel import PLATFORM_SCHEMA
from homeassistant.components.ifttt import (
    ATTR_EVENT, DOMAIN as IFTTT_DOMAIN, SERVICE_TRIGGER)
from homeassistant.const import STATE_ALARM_DISARMED, CONF_NAME, CONF_CODE
import homeassistant.helpers.config_validation as cv

DEPENDENCIES = ['ifttt']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Home"

EVENT_ALARM_ARM_AWAY = "alarm_arm_away"
EVENT_ALARM_ARM_HOME = "alarm_arm_home"
EVENT_ALARM_ARM_NIGHT = "alarm_arm_night"
EVENT_ALARM_DISARM = "alarm_disarm"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_CODE): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up a control panel managed through IFTTT."""
    name = config.get(CONF_NAME)
    code = config.get(CONF_CODE)

    alarmpanel = IFTTTAlarmPanel(hass, name, code)
    add_devices([alarmpanel])


class IFTTTAlarmPanel(alarm.AlarmControlPanel):
    """Representation of an alarm control panel controlled throught IFTTT."""

    def __init__(self, hass, name, code):
        """Initialize the alarm control panel."""
        self._hass = hass
        self._name = name
        self._code = code
        # Set default state to disarmed
        self._state = STATE_ALARM_DISARMED

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def assumed_state(self):
        """Notify that this platform return an assumed state."""
        return True

    @property
    def code_format(self):
        """Return one or more characters."""
        return None if self._code is None else '.+'

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        if not self._check_code(code):
            return
        self.set_alarm_state(EVENT_ALARM_DISARM, code)

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        if not self._check_code(code):
            return
        self.set_alarm_state(EVENT_ALARM_ARM_AWAY, code)

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        if not self._check_code(code):
            return
        self.set_alarm_state(EVENT_ALARM_ARM_HOME, code)

    def alarm_arm_night(self, code=None):
        """Send arm night command."""
        if not self._check_code(code):
            return
        self.set_alarm_state(EVENT_ALARM_ARM_NIGHT, code)

    def set_alarm_state(self, event, code):
        """Call the IFTTT trigger service to change the alarm state."""
        data = {ATTR_EVENT: event}

        self._hass.services.call(IFTTT_DOMAIN, SERVICE_TRIGGER, data)
        _LOGGER.debug("Called IFTTT component to trigger event %s", event)

    def _check_code(self, code):
        return self._code is None or self._code == code
