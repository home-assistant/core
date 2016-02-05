"""
Networx NX584 interface
~~~~~~~~~~~~~~~~~~~~~~~

Configuration:

To use the Example custom component you will need to add the following to
your configuration.yaml file.

alarm_control_panel:
  platform: nx584
  host: localhost:5007

Variable:

host
*Optional
HOST should be a something like "localhost:5007" which is the
connection information for talking to the pynx584 backend server.
"""
import logging
import requests

from homeassistant.const import (STATE_UNKNOWN, STATE_ALARM_DISARMED,
                                 STATE_ALARM_ARMED_HOME,
                                 STATE_ALARM_ARMED_AWAY)
import homeassistant.components.alarm_control_panel as alarm

REQUIREMENTS = ['pynx584==0.1']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Setup nx584. """
    host = config.get('host', 'localhost:5007')

    try:
        add_devices([NX584Alarm(hass, host, config.get('name', 'NX584'))])
    except requests.exceptions.ConnectionError as ex:
        _LOGGER.error('Unable to connect to NX584: %s', str(ex))
        return False


class NX584Alarm(alarm.AlarmControlPanel):
    """ NX584-based alarm panel. """
    def __init__(self, hass, host, name):
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
        return True

    @property
    def name(self):
        return self._name

    @property
    def code_format(self):
        return '[0-9]{4}([0-9]{2})?'

    @property
    def state(self):
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
        self._alarm.disarm(code)

    def alarm_arm_home(self, code=None):
        self._alarm.arm('home')

    def alarm_arm_away(self, code=None):
        self._alarm.arm('auto')

    def alarm_trigger(self, code=None):
        raise NotImplementedError()
