"""
Support for Speedtest.net.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.speedtest/
"""
import asyncio
import logging
import re
import sys
from subprocess import check_output, CalledProcessError

import voluptuous as vol

import homeassistant.util.dt as dt_util
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import (DOMAIN, PLATFORM_SCHEMA)
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_time_change
from homeassistant.helpers.restore_state import async_get_last_state

REQUIREMENTS = ['speedtest-cli==1.0.6']

_LOGGER = logging.getLogger(__name__)
_SPEEDTEST_REGEX = re.compile(r'Ping:\s(\d+\.\d+)\sms[\r\n]+'
                              r'Download:\s(\d+\.\d+)\sMbit/s[\r\n]+'
                              r'Upload:\s(\d+\.\d+)\sMbit/s[\r\n]+')

CONF_SECOND = 'second'
CONF_MINUTE = 'minute'
CONF_HOUR = 'hour'
CONF_DAY = 'day'
CONF_SERVER_ID = 'server_id'
CONF_MANUAL = 'manual'

ICON = 'mdi:speedometer'

SENSOR_TYPES = {
    'ping': ['Ping', 'ms'],
    'download': ['Download', 'Mbit/s'],
    'upload': ['Upload', 'Mbit/s'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MONITORED_CONDITIONS):
        vol.All(cv.ensure_list, [vol.In(list(SENSOR_TYPES))]),
    vol.Optional(CONF_SERVER_ID): cv.positive_int,
    vol.Optional(CONF_SECOND, default=[0]):
        vol.All(cv.ensure_list, [vol.All(vol.Coerce(int), vol.Range(0, 59))]),
    vol.Optional(CONF_MINUTE, default=[0]):
        vol.All(cv.ensure_list, [vol.All(vol.Coerce(int), vol.Range(0, 59))]),
    vol.Optional(CONF_HOUR):
        vol.All(cv.ensure_list, [vol.All(vol.Coerce(int), vol.Range(0, 23))]),
    vol.Optional(CONF_DAY):
        vol.All(cv.ensure_list, [vol.All(vol.Coerce(int), vol.Range(1, 31))]),
    vol.Optional(CONF_MANUAL, default=False): cv.boolean,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Speedtest sensor."""
    data = SpeedtestData(hass, config)
    dev = []
    for sensor in config[CONF_MONITORED_CONDITIONS]:
        if sensor not in SENSOR_TYPES:
            _LOGGER.error("Sensor type: %s does not exist", sensor)
        else:
            dev.append(SpeedtestSensor(data, sensor))

    add_devices(dev)

    def update(call=None):
        """Update service for manual updates."""
        data.update(dt_util.now())
        for sensor in dev:
            sensor.update()

    hass.services.register(DOMAIN, 'update_speedtest', update)


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

    @property
    def icon(self):
        """Return icon."""
        return ICON

    def update(self):
        """Get the latest data and update the states."""
        data = self.speedtest_client.data
        if data is None:
            return

        if self.type == 'ping':
            self._state = data['ping']
        elif self.type == 'download':
            self._state = data['download']
        elif self.type == 'upload':
            self._state = data['upload']

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Handle all entity which are about to be added."""
        state = yield from async_get_last_state(self.hass, self.entity_id)
        if not state:
            return
        self._state = state.state


class SpeedtestData(object):
    """Get the latest data from speedtest.net."""

    def __init__(self, hass, config):
        """Initialize the data object."""
        self.data = None
        self._server_id = config.get(CONF_SERVER_ID)
        if not config.get(CONF_MANUAL):
            track_time_change(
                hass, self.update, second=config.get(CONF_SECOND),
                minute=config.get(CONF_MINUTE), hour=config.get(CONF_HOUR),
                day=config.get(CONF_DAY))

    def update(self, now):
        """Get the latest data from speedtest.net."""
        import speedtest

        _LOGGER.info("Executing speedtest...")
        try:
            args = [sys.executable, speedtest.__file__, '--simple']
            if self._server_id:
                args = args + ['--server', str(self._server_id)]

            re_output = _SPEEDTEST_REGEX.split(
                check_output(args).decode('utf-8'))
        except CalledProcessError as process_error:
            _LOGGER.error("Error executing speedtest: %s", process_error)
            return
        self.data = {
            'ping': round(float(re_output[1]), 2),
            'download': round(float(re_output[2]), 2),
            'upload': round(float(re_output[3]), 2),
        }
