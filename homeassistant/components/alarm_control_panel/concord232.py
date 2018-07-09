"""
Support for Concord232 alarm control panels.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.concord232/
"""
import datetime
from datetime import timedelta
import logging

import requests
import voluptuous as vol

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.alarm_control_panel import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PORT, STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED, STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['concord232==0.15']

_LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = 'localhost'
DEFAULT_NAME = 'CONCORD232'
DEFAULT_PORT = 5007

SCAN_INTERVAL = timedelta(seconds=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Concord232 alarm control panel platform."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)

    url = 'http://{}:{}'.format(host, port)

    try:
        add_devices([Concord232Alarm(hass, url, name)])
    except requests.exceptions.ConnectionError as ex:
        _LOGGER.error("Unable to connect to Concord232: %s", str(ex))
        return


class Concord232Alarm(alarm.AlarmControlPanel):
    """Representation of the Concord232-based alarm panel."""

    def __init__(self, hass, url, name):
        """Initialize the Concord232 alarm panel."""
        from concord232 import client as concord232_client

        self._state = STATE_UNKNOWN
        self._hass = hass
        self._name = name
        self._url = url

        try:
            client = concord232_client.Client(self._url)
        except requests.exceptions.ConnectionError as ex:
            _LOGGER.error("Unable to connect to Concord232: %s", str(ex))

        self._alarm = client
        self._alarm.partitions = self._alarm.list_partitions()
        self._alarm.last_partition_update = datetime.datetime.now()
        self.update()

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def code_format(self):
        """Return the characters if code is defined."""
        return 'Number'

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    def update(self):
        """Update values from API."""
        try:
            part = self._alarm.list_partitions()[0]
        except requests.exceptions.ConnectionError as ex:
            _LOGGER.error("Unable to connect to %(host)s: %(reason)s",
                          dict(host=self._url, reason=ex))
            newstate = STATE_UNKNOWN
        except IndexError:
            _LOGGER.error("Concord232 reports no partitions")
            newstate = STATE_UNKNOWN

        if part['arming_level'] == 'Off':
            newstate = STATE_ALARM_DISARMED
        elif 'Home' in part['arming_level']:
            newstate = STATE_ALARM_ARMED_HOME
        else:
            newstate = STATE_ALARM_ARMED_AWAY

        if not newstate == self._state:
            _LOGGER.info("State change from %s to %s", self._state, newstate)
            self._state = newstate
        return self._state

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        self._alarm.disarm(code)

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        self._alarm.arm('stay')

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        self._alarm.arm('away')
