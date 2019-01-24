"""
Support for Concord232 alarm control panels.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.concord232/
"""
import datetime
import logging

import requests
import voluptuous as vol

import homeassistant.components.alarm_control_panel as alarm
import homeassistant.helpers.config_validation as cv
from homeassistant.components.alarm_control_panel import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PORT, STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED)

REQUIREMENTS = ['concord232==0.15']

_LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = 'localhost'
DEFAULT_NAME = 'CONCORD232'
DEFAULT_PORT = 5007

SCAN_INTERVAL = datetime.timedelta(seconds=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Concord232 alarm control panel platform."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)

    url = 'http://{}:{}'.format(host, port)

    try:
        add_entities([Concord232Alarm(url, name)], True)
    except requests.exceptions.ConnectionError as ex:
        _LOGGER.error("Unable to connect to Concord232: %s", str(ex))


class Concord232Alarm(alarm.AlarmControlPanel):
    """Representation of the Concord232-based alarm panel."""

    def __init__(self, url, name):
        """Initialize the Concord232 alarm panel."""
        from concord232 import client as concord232_client

        self._state = None
        self._name = name
        self._url = url
        self._alarm = concord232_client.Client(self._url)
        self._alarm.partitions = self._alarm.list_partitions()
        self._alarm.last_partition_update = datetime.datetime.now()

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def code_format(self):
        """Return the characters if code is defined."""
        return alarm.FORMAT_NUMBER

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
            return
        except IndexError:
            _LOGGER.error("Concord232 reports no partitions")
            return

        if part['arming_level'] == 'Off':
            self._state = STATE_ALARM_DISARMED
        elif 'Home' in part['arming_level']:
            self._state = STATE_ALARM_ARMED_HOME
        else:
            self._state = STATE_ALARM_ARMED_AWAY

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        self._alarm.disarm(code)

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        self._alarm.arm('stay')

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        self._alarm.arm('away')
