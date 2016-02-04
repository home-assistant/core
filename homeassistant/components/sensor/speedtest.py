"""
homeassistant.components.sensor.speedtest
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Speedtest.net sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.speedtest/
"""
import logging
import re
from datetime import timedelta
from subprocess import check_output
from homeassistant.util import Throttle
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['speedtest-cli==0.3.4']
_LOGGER = logging.getLogger(__name__)

_SPEEDTEST_REGEX = re.compile('Ping:\s(\d+\.\d+)\sms\\nDownload:\s(\d+\.\d+)'
                              '\sMbit/s\\nUpload:\s(\d+\.\d+)\sMbit/s\\n')

SENSOR_TYPES = {
    'ping': ['Ping', 'ms'],
    'download': ['Download', 'Mbit/s'],
    'upload': ['Upload', 'Mbit/s'],
}

# Return cached results if last scan was less then this time ago
MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=3600)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Setup the Speedtest sensor. """

    data = SpeedtestData()

    dev = []
    for variable in config['monitored_conditions']:
        if variable not in SENSOR_TYPES:
            _LOGGER.error('Sensor type: "%s" does not exist', variable)
        else:
            dev.append(SpeedtestSensor(data, variable))

    add_devices(dev)


# pylint: disable=too-few-public-methods
class SpeedtestSensor(Entity):
    """ Implements a speedtest.net sensor. """

    def __init__(self, speedtest_data, sensor_type):
        self.client_name = 'Speedtest'
        self._name = SENSOR_TYPES[sensor_type][0]
        self.speedtest_client = speedtest_data
        self.type = sensor_type
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[self.type][1]
        self.update()

    @property
    def name(self):
        return '{} {}'.format(self.client_name, self._name)

    @property
    def state(self):
        """ Returns the state of the device. """
        return self._state

    @property
    def unit_of_measurement(self):
        """ Unit of measurement of this entity, if any. """
        return self._unit_of_measurement

    # pylint: disable=too-many-branches
    def update(self):
        """ Gets the latest data from Forecast.io and updates the states. """
        self.speedtest_client.update()
        data = self.speedtest_client.data

        if self.type == 'ping':
            self._state = data['ping']
        elif self.type == 'download':
            self._state = data['download']
        elif self.type == 'upload':
            self._state = data['upload']


class SpeedtestData(object):
    """ Gets the latest data from speedtest.net. """

    def __init__(self):
        self.data = None
        self.update()

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """ Gets the latest data from speedtest.net. """
        _LOGGER.info('Executing speedtest')
        re_output = _SPEEDTEST_REGEX.split(
            check_output(["speedtest-cli", "--simple"]).decode("utf-8"))
        self.data = {'ping': re_output[1], 'download': re_output[2],
                     'upload': re_output[3]}
