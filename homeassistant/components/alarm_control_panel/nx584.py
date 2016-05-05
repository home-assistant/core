"""
Support for NX584 alarm control panels.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/alarm_control_panel.nx584/
"""
import logging

import requests

import homeassistant.components.alarm_control_panel as alarm
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY, STATE_ALARM_ARMED_HOME, STATE_ALARM_DISARMED,
    STATE_UNKNOWN)

REQUIREMENTS = ['pynx584==0.2']
_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup nx584 platform."""
    host = config.get('host', 'localhost:5007')

    try:
        add_devices([NX584Alarm(hass, host, config.get('name', 'NX584'))])
    except requests.exceptions.ConnectionError as ex:
        _LOGGER.error('Unable to connect to NX584: %s', str(ex))
        return False


class NX584Alarm(alarm.AlarmControlPanel):
    """Represents the NX584-based alarm panel."""

    def __init__(self, hass, host, name):
        """Initalize the nx584 alarm panel."""
        from nx584 import client
        self._hass = hass
        self._host = host
        self._name = name
        self._alarm = client.Client('http://%s' % host)
        # Do an initial list operation so that we will try to actually
        # talk to the API and trigger a requests exception for setup_platform()
        # to catch
        self._alarm.list_zones()

    @property
    def should_poll(self):
        """Polling needed."""
        return True

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def code_format(self):
        """The characters if code is defined."""
        return '[0-9]{4}([0-9]{2})?'

    @property
    def state(self):
        """Return the state of the device."""
        try:
            part = self._alarm.list_partitions()[0]
            zones = self._alarm.list_zones()
        except requests.exceptions.ConnectionError as ex:
            _LOGGER.error('Unable to connect to %(host)s: %(reason)s',
                          dict(host=self._host, reason=ex))
            return STATE_UNKNOWN
        except IndexError:
            _LOGGER.error('nx584 reports no partitions')
            return STATE_UNKNOWN

        bypassed = False
        for zone in zones:
            if zone['bypassed']:
                _LOGGER.debug('Zone %(zone)s is bypassed, '
                              'assuming HOME',
                              dict(zone=zone['number']))
                bypassed = True
                break

        if not part['armed']:
            return STATE_ALARM_DISARMED
        elif bypassed:
            return STATE_ALARM_ARMED_HOME
        else:
            return STATE_ALARM_ARMED_AWAY

    def alarm_disarm(self, code=None):
        """Send disarm command."""
        self._alarm.disarm(code)

    def alarm_arm_home(self, code=None):
        """Send arm home command."""
        self._alarm.arm('home')

    def alarm_arm_away(self, code=None):
        """Send arm away command."""
        self._alarm.arm('auto')

    def alarm_trigger(self, code=None):
        """Alarm trigger command."""
        raise NotImplementedError()
