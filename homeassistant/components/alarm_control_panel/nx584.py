"""
Support for NX584 alarm control panels.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.nx584/
"""
import logging

import requests
import voluptuous as vol

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.components.alarm_control_panel import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PORT, STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED, STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['pynx584==0.4']

_LOGGER = logging.getLogger(__name__)

DEFAULT_HOST = 'localhost'
DEFAULT_NAME = 'NX584'
DEFAULT_PORT = 5007

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the NX584 platform."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)

    url = 'http://{}:{}'.format(host, port)

    try:
        add_devices([NX584Alarm(hass, url, name)])
    except requests.exceptions.ConnectionError as ex:
        _LOGGER.error("Unable to connect to NX584: %s", str(ex))
        return False


class NX584Alarm(alarm.AlarmControlPanel):
    """Representation of a NX584-based alarm panel."""

    def __init__(self, hass, url, name):
        """Init the nx584 alarm panel."""
        from nx584 import client
        self._hass = hass
        self._name = name
        self._url = url
        self._alarm = client.Client(self._url)
        # Do an initial list operation so that we will try to actually
        # talk to the API and trigger a requests exception for setup_platform()
        # to catch
        self._alarm.list_zones()
        self._state = STATE_UNKNOWN

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def code_format(self):
        """Return che characters if code is defined."""
        return '[0-9]{4}([0-9]{2})?'

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    def update(self):
        """Process new events from panel."""
        try:
            part = self._alarm.list_partitions()[0]
            zones = self._alarm.list_zones()
        except requests.exceptions.ConnectionError as ex:
            _LOGGER.error("Unable to connect to %(host)s: %(reason)s",
                          dict(host=self._url, reason=ex))
            self._state = STATE_UNKNOWN
            zones = []
        except IndexError:
            _LOGGER.error("NX584 reports no partitions")
            self._state = STATE_UNKNOWN
            zones = []

        bypassed = False
        for zone in zones:
            if zone['bypassed']:
                _LOGGER.debug("Zone %(zone)s is bypassed, assuming HOME",
                              dict(zone=zone['number']))
                bypassed = True
                break

        if not part['armed']:
            self._state = STATE_ALARM_DISARMED
        elif bypassed:
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
        self._alarm.arm('exit')
