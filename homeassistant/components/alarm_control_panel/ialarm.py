"""
Interfaces with iAlarm control panels.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.ialarm/
"""
import logging

import voluptuous as vol

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.alarm_control_panel import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME, STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pyialarm==0.2']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'iAlarm'


def no_application_protocol(value):
    """Validate that value is without the application protocol."""
    protocol_separator = "://"
    if not value or protocol_separator in value:
        raise vol.Invalid(
            'Invalid host, {} is not allowed'.format(protocol_separator))

    return value


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): vol.All(cv.string, no_application_protocol),
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_USERNAME): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up an iAlarm control panel."""
    name = config.get(CONF_NAME)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    host = config.get(CONF_HOST)

    url = 'http://{}'.format(host)
    ialarm = IAlarmPanel(name, username, password, url)
    add_devices([ialarm], True)


class IAlarmPanel(alarm.AlarmControlPanel):
    """Representation of an iAlarm status."""

    def __init__(self, name, username, password, url):
        """Initialize the iAlarm status."""
        from pyialarm import IAlarm

        self._name = name
        self._username = username
        self._password = password
        self._url = url
        self._state = None
        self._client = IAlarm(username, password, url)

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
        status = self._client.get_status()
        _LOGGER.debug('iAlarm status: %s', status)
        if status:
            status = int(status)

        if status == self._client.DISARMED:
            state = STATE_ALARM_DISARMED
        elif status == self._client.ARMED_AWAY:
            state = STATE_ALARM_ARMED_AWAY
        elif status == self._client.ARMED_STAY:
            state = STATE_ALARM_ARMED_HOME
        else:
            state = None

        self._state = state

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        self._client.disarm()

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        self._client.arm_away()

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        self._client.arm_stay()
