"""Interfaces with TotalConnect alarm control panels."""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.alarm_control_panel import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_PASSWORD, CONF_USERNAME, STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME, STATE_ALARM_ARMED_NIGHT, STATE_ALARM_DISARMED,
    STATE_ALARM_ARMING, STATE_ALARM_DISARMING, CONF_NAME,
    STATE_ALARM_ARMED_CUSTOM_BYPASS)


_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Total Connect'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a TotalConnect control panel."""
    name = config.get(CONF_NAME)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    total_connect = TotalConnect(name, username, password)
    add_entities([total_connect], True)


class TotalConnect(alarm.AlarmControlPanel):
    """Represent an TotalConnect status."""

    def __init__(self, name, username, password):
        """Initialize the TotalConnect status."""
        from total_connect_client import TotalConnectClient

        _LOGGER.debug("Setting up TotalConnect...")
        self._name = name
        self._username = username
        self._password = password
        self._state = None
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
        elif status == self._client.ARMED_STAY_NIGHT:
            state = STATE_ALARM_ARMED_NIGHT
        elif status == self._client.ARMED_CUSTOM_BYPASS:
            state = STATE_ALARM_ARMED_CUSTOM_BYPASS
        elif status == self._client.ARMING:
            state = STATE_ALARM_ARMING
        elif status == self._client.DISARMING:
            state = STATE_ALARM_DISARMING
        else:
            state = None

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

    def alarm_arm_night(self, code=None):
        """Send arm night command."""
        self._client.arm_stay_night()
