"""
Interfaces with TotalConnect alarm control panels.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.totalconnect/
"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.alarm_control_panel import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_PASSWORD, CONF_USERNAME, STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED, STATE_UNKNOWN,
    CONF_NAME)

REQUIREMENTS = ['total_connect_client==0.7']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Total Connect'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up a TotalConnect control panel."""
    name = config.get(CONF_NAME)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    total_connect = TotalConnect(name, username, password)
    add_devices([total_connect], True)


class TotalConnect(alarm.AlarmControlPanel):
    """Represent an TotalConnect status."""

    def __init__(self, name, username, password):
        """Initialize the TotalConnect status."""
        from total_connect_client import TotalConnectClient

        _LOGGER.debug("Setting up TotalConnect...")
        self._name = name
        self._username = username
        self._password = password
        self._state = STATE_UNKNOWN
        self._client = TotalConnectClient.TotalConnectClient(
            username, password)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    def update(self):
        """Return the state of the device."""
        status = self._client.get_armed_status()

        if status == self._client.DISARMED:
            state = STATE_ALARM_DISARMED
        elif status == self._client.ARMED_STAY:
            state = STATE_ALARM_ARMED_HOME
        elif status == self._client.ARMED_AWAY:
            state = STATE_ALARM_ARMED_AWAY
        else:
            state = STATE_UNKNOWN

        self._state = state

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        self._client.disarm()

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        self._client.arm_stay()

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        self._client.arm_away()
