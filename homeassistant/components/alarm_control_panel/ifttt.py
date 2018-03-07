"""
Interfaces with alarm control panels that have to be controlled through IFTTT.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.ifttt_securitysystem/
"""
import logging
import voluptuous as vol

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.alarm_control_panel import PLATFORM_SCHEMA
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY, SERVICE_ALARM_ARM_AWAY,
    STATE_ALARM_ARMED_HOME, SERVICE_ALARM_ARM_HOME,
    STATE_ALARM_ARMED_NIGHT, SERVICE_ALARM_ARM_NIGHT,
    STATE_ALARM_DISARMED, SERVICE_ALARM_DISARM,
    CONF_NAME)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['requests>=2.18.4', 'pyfttt>=0.3']

_LOGGER = logging.getLogger(__name__)

CONF_WEBHOOK_KEY = "webhook_key"
DEFAULT_NAME = "Home"

STATE_TO_SERVICE = {
    STATE_ALARM_ARMED_AWAY: SERVICE_ALARM_ARM_AWAY,
    STATE_ALARM_ARMED_HOME: SERVICE_ALARM_ARM_HOME,
    STATE_ALARM_ARMED_NIGHT: SERVICE_ALARM_ARM_NIGHT,
    STATE_ALARM_DISARMED: SERVICE_ALARM_DISARM}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_WEBHOOK_KEY): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up a control panel managed through IFTTT."""
    name = config.get(CONF_NAME)
    webhook_key = config.get(CONF_WEBHOOK_KEY)

    alarmpanel = IFTTTAlarmPanel(name, webhook_key)
    add_devices([alarmpanel], True)


class IFTTTAlarmPanel(alarm.AlarmControlPanel):
    """Representation of an alarm control panel controlled throught IFTTT."""

    def __init__(self, name, webhook_key):
        """Initialize the alarm control panel."""

        self._name = name
        self._webhook_key = webhook_key
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

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        self.set_alarm_state(STATE_ALARM_DISARMED)

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        self.set_alarm_state(STATE_ALARM_ARMED_AWAY)

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        self.set_alarm_state(STATE_ALARM_ARMED_HOME)

    def alarm_arm_night(self, code=None):
        """Send arm night command."""
        self.set_alarm_state(STATE_ALARM_ARMED_NIGHT)

    def set_alarm_state(self, state):
        """Call the IFTTT webhook to change the alarm state."""
        import pyfttt
        import requests

        try:
            # Translate the state to a service/event name
            event = STATE_TO_SERVICE[state]

            # Send the webhook request
            pyfttt.send_event(self._webhook_key, event)
            # IFTTT should be configured to also call the API to change state

            _LOGGER.debug("Called IFTTT webhook to set state {}", state)
        except requests.exceptions.RequestException:
            _LOGGER.exception("Error communicating with IFTTT")
