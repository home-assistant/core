"""
Support for Ebusd daemon for communication with eBUS heating systems.
For more details about ebusd, please refer to the documentation at
https://github.com/john30/ebusd
"""

from datetime import timedelta
from datetime import datetime
import logging
import socket

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_HOST, CONF_PORT, CONF_MONITORED_VARIABLES, STATE_ON, STATE_OFF, STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'ebusd'
DEFAULT_PORT = 8888
CONF_CIRCUIT = 'circuit'
CACHE_TTL = 900

BASE_COMMAND = 'read -m {2} -c {0} {1}\n'

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=15)

SENSOR_TYPES = {
    'hc1ActualFlowTempDesired': ['Hc1ActualFlowTempDesired', '°C', 'mdi:thermometer', 'decimal'],
    'hc1MaxFlowTempDesired': ['Hc1MaxFlowTempDesired', '°C', 'mdi:thermometer', 'decimal'],
    'hc1MinFlowTempDesired': ['Hc1MinFlowTempDesired', '°C', 'mdi:thermometer', 'decimal'],
    'hc1PumpStatus': ['Hc1PumpStatus', None, 'mdi:toggle-switch', 'switch'],
    'hc1SummerTempLimit': ['Hc1SummerTempLimit', '°C', 'mdi:weather-sunny', 'decimal'],
    'holidayTemp': ['HolidayTemp', '°C', 'mdi:thermometer', 'decimal'],
    'hwcTempDesired': ['HwcTempDesired', '°C', 'mdi:thermometer', 'decimal'],
    'hwcTimerMonday': ['hwcTimer.Monday', None, 'mdi:timer', 'time-schedule'],
    'hwcTimerTuesday': ['hwcTimer.Tuesday', None, 'mdi:timer', 'time-schedule'],
    'hwcTimerWednesday': ['hwcTimer.Wednesday', None, 'mdi:timer', 'time-schedule'],
    'hwcTimerThursday': ['hwcTimer.Thursday', None, 'mdi:timer', 'time-schedule'],
    'hwcTimerFriday': ['hwcTimer.Friday', None, 'mdi:timer', 'time-schedule'],
    'hwcTimerSaturday': ['hwcTimer.Saturday', None, 'mdi:timer', 'time-schedule'],
    'hwcTimerSunday': ['hwcTimer.Sunday', None, 'mdi:timer', 'time-schedule'],
    'waterPressure': ['WaterPressure', 'bar', 'mdi:water-pump', 'decimal'],
    'z1RoomZoneMapping': ['z1RoomZoneMapping', None, 'mdi:label', 'decimal'],
    'z1NightTemp': ['z1NightTemp', '°C', 'mdi:weather-night', 'decimal'],
    'z1DayTemp': ['z1DayTemp', '°C', 'mdi:weather-sunny', 'decimal'],
    'z1HolidayTemp': ['z1HolidayTemp', '°C', 'mdi:thermometer', 'decimal'],
    'z1RoomTemp': ['z1RoomTemp', '°C', 'mdi:thermometer', 'decimal'],
    'z1ActualRoomTempDesired': ['z1ActualRoomTempDesired', '°C', 'mdi:thermometer', 'decimal'],
    'z1TimerMonday': ['z1Timer.Monday', None, 'mdi:timer', 'time-schedule'],
    'z1TimerTuesday': ['z1Timer.Tuesday', None, 'mdi:timer', 'time-schedule'],
    'z1TimerWednesday': ['z1Timer.Wednesday', None, 'mdi:timer', 'time-schedule'],
    'z1TimerThursday': ['z1Timer.Thursday', None, 'mdi:timer', 'time-schedule'],
    'z1TimerFriday': ['z1Timer.Friday', None, 'mdi:timer', 'time-schedule'],
    'z1TimerSaturday': ['z1Timer.Saturday', None, 'mdi:timer', 'time-schedule'],
    'z1TimerSunday': ['z1Timer.Sunday', None, 'mdi:timer', 'time-schedule'],
    'continuosHeating': ['ContinuosHeating', '°C', 'mdi:weather-snowy', 'decimal'],
    'prEnergySumHcLastMonth': ['PrEnergySumHcLastMonth', 'kWh', 'mdi:flash', 'decimal'],
    'prEnergySumHcThisMonth': ['PrEnergySumHcThisMonth', 'kWh', 'mdi:flash', 'decimal']
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_CIRCUIT): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_MONITORED_VARIABLES, default=[]): vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)])
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Ebusd..."""
    name = config.get(CONF_NAME)
    circuit = config.get(CONF_CIRCUIT)
    server_address = (config.get(CONF_HOST), config.get(CONF_PORT))

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        data = EbusdData(server_address, circuit)

        sock.settimeout(5)
        sock.connect(server_address)
        sock.close()

        dev = []
        for variable in config[CONF_MONITORED_VARIABLES]:
            dev.append(Ebusd(data, variable, name))
        
        add_devices(dev)
    except socket.timeout:
        _LOGGER.error("socket timeout error")
        return
    except socket.error:
        _LOGGER.error("socket error")
        return


def timer_format(string):
    r = []
    s = string.split(';')
    for i in range(0, len(s) // 2):
        if(s[i * 2] != '-:-' and s[i * 2] != s[(i * 2) + 1]):
            r.append(s[i * 2] + '/' + s[(i * 2) + 1])
    return ' - '.join(r)


class EbusdData(object):
    """Get the latest data from Ebusd."""

    def __init__(self, address, circuit):
        """Initialize the data object."""
        self._circuit = circuit
        self._address = address
        self.value = {}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self, name):
        """Call the Ebusd API to update the data."""
        command = BASE_COMMAND.format(self._circuit, name, CACHE_TTL)

        try:
            _LOGGER.debug("Opening socket connection to ebusd %s: %s", name, command)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect(self._address)

            sock.sendall(command.encode())
            command_result = sock.recv(256).decode('utf-8').rstrip()
            if 'not found' in command_result:
                _LOGGER.warning('Element not found: %s', name)
                raise RuntimeError('Element not found')
            else:
                self.value[name] = command_result
        except socket.timeout:
            _LOGGER.error("socket timeout error")
            raise RuntimeError('socket timeout')
        except socket.error:
            _LOGGER.error()
            raise RuntimeError('Command failed')
        finally:
            sock.close()


class Ebusd(Entity):
    """Representation of a Sensor."""

    def __init__(self, data, sensor_type, name):
        """Initialize the sensor."""
        self._state = None
        self._client_name = name
        self._name = SENSOR_TYPES[sensor_type][0]
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._icon = SENSOR_TYPES[sensor_type][2]
        self._type = SENSOR_TYPES[sensor_type][3]
        self.data = data

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self._client_name, self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    def update(self):
        """Fetch new state data for the sensor."""
        try:
            self.data.update(self._name)
            if self._name in self.data.value:
                if self._type == 'switch':
                    self._state = STATE_ON if self.data.value[self._name] == 1 else STATE_OFF
                elif self._type == 'time-schedule':
                    self._state = timer_format(self.data.value[self._name])
                elif self._type == 'decimal':
                    self._state = format(float(self.data.value[self._name]), '.1f')
        except RuntimeError:
            _LOGGER.debug("EbusdData.update exception")
