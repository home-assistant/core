"""
Support for Speedtest.net based on speedtest-cli.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.speedtest/
"""
import logging
import re
import sys
from subprocess import check_output

import homeassistant.util.dt as dt_util
from homeassistant.components.sensor import DOMAIN
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_time_change

REQUIREMENTS = ['speedtest-cli==0.3.4']
_LOGGER = logging.getLogger(__name__)

_SPEEDTEST_REGEX = re.compile(r'Ping:\s(\d+\.\d+)\sms[\r\n]+'
                              r'Download:\s(\d+\.\d+)\sMbit/s[\r\n]+'
                              r'Upload:\s(\d+\.\d+)\sMbit/s[\r\n]+')

CONF_MONITORED_CONDITIONS = 'monitored_conditions'
CONF_SECOND = 'second'
CONF_MINUTE = 'minute'
CONF_HOUR = 'hour'
CONF_DAY = 'day'
SENSOR_TYPES = {
    'ping': ['Ping', 'ms'],
    'download': ['Download', 'Mbit/s'],
    'upload': ['Upload', 'Mbit/s'],
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Speedtest sensor."""
    data = SpeedtestData(hass, config)
    dev = []
    for sensor in config[CONF_MONITORED_CONDITIONS]:
        if sensor not in SENSOR_TYPES:
            _LOGGER.error('Sensor type: "%s" does not exist', sensor)
        else:
            dev.append(SpeedtestSensor(data, sensor))

    add_devices(dev)

    def update(call=None):
        """Update service for manual updates."""
        data.update(dt_util.now())
        for sensor in dev:
            sensor.update()

    hass.services.register(DOMAIN, 'update_speedtest', update)


# pylint: disable=too-few-public-methods
class SpeedtestSensor(Entity):
    """Implementation of a speedtest.net sensor."""

    def __init__(self, speedtest_data, sensor_type):
        """Initialize the sensor."""
        self._name = SENSOR_TYPES[sensor_type][0]
        self.speedtest_client = speedtest_data
        self.type = sensor_type
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[self.type][1]

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format('Speedtest', self._name)

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    def update(self):
        """Get the latest data and update the states."""
        data = self.speedtest_client.data
        if data is None:
            return

        elif self.type == 'ping':
            self._state = data['ping']
        elif self.type == 'download':
            self._state = data['download']
        elif self.type == 'upload':
            self._state = data['upload']


class SpeedtestData(object):
    """Get the latest data from speedtest.net."""

    def __init__(self, hass, config):
        """Initialize the data object."""
        self.data = None
        track_time_change(hass, self.update,
                          second=config.get(CONF_SECOND, 0),
                          minute=config.get(CONF_MINUTE, 0),
                          hour=config.get(CONF_HOUR, None),
                          day=config.get(CONF_DAY, None))

    def update(self, now):
        """Get the latest data from speedtest.net."""
        import speedtest_cli

        _LOGGER.info('Executing speedtest')
        re_output = _SPEEDTEST_REGEX.split(
            check_output([sys.executable, speedtest_cli.__file__,
                          '--simple']).decode("utf-8"))
        self.data = {'ping': round(float(re_output[1]), 2),
                     'download': round(float(re_output[2]), 2),
                     'upload': round(float(re_output[3]), 2)}
