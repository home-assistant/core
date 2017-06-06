"""
Support for Neato Connected Vaccums sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.neato/
"""
import logging
import requests
from homeassistant.helpers.entity import Entity
from homeassistant.components.neato import (
    NEATO_ROBOTS, NEATO_LOGIN, NEATO_MAP_DATA, ACTION, ERRORS, MODE, ALERTS)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['neato']

SENSOR_TYPE_STATUS = 'status'
SENSOR_TYPE_BATTERY = 'battery'

SENSOR_TYPES = {
    SENSOR_TYPE_STATUS: ['Status'],
    SENSOR_TYPE_BATTERY: ['Battery']
}

ATTR_CLEAN_START = 'clean_start'
ATTR_CLEAN_STOP = 'clean_stop'
ATTR_CLEAN_AREA = 'clean_area'
ATTR_CLEAN_BATTERY_START = 'battery_level_at_clean_start'
ATTR_CLEAN_BATTERY_END = 'battery_level_at_clean_end'
ATTR_CLEAN_SUSP_COUNT = 'clean_suspension_count'
ATTR_CLEAN_SUSP_TIME = 'clean_suspension_time'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Neato sensor platform."""
    dev = []
    for robot in hass.data[NEATO_ROBOTS]:
        for type_name in SENSOR_TYPES:
            dev.append(NeatoConnectedSensor(hass, robot, type_name))
    _LOGGER.debug("Adding sensors %s", dev)
    add_devices(dev)


class NeatoConnectedSensor(Entity):
    """Neato Connected Sensor."""

    def __init__(self, hass, robot, sensor_type):
        """Initialize the Neato Connected sensor."""
        self.type = sensor_type
        self.robot = robot
        self.neato = hass.data[NEATO_LOGIN]
        self._robot_name = self.robot.name + ' ' + SENSOR_TYPES[self.type][0]
        self._status_state = None
        try:
            self._state = self.robot.state
        except (requests.exceptions.ConnectionError,
                requests.exceptions.HTTPError) as ex:
            self._state = None
            _LOGGER.warning("Neato connection error: %s", ex)
        self._mapdata = hass.data[NEATO_MAP_DATA]
        self.clean_time_start = None
        self.clean_time_stop = None
        self.clean_area = None
        self.clean_battery_start = None
        self.clean_battery_end = None
        self.clean_suspension_charge_count = None
        self.clean_suspension_time = None
        self._battery_state = None

    def update(self):
        """Update the properties of sensor."""
        _LOGGER.debug('Update of sensor')
        self.neato.update_robots()
        self._mapdata = self.hass.data[NEATO_MAP_DATA]
        try:
            self._state = self.robot.state
        except (requests.exceptions.ConnectionError,
                requests.exceptions.HTTPError) as ex:
            self._state = None
            self._status_state = 'Offline'
            _LOGGER.warning("Neato connection error: %s", ex)
            return
        if not self._state:
            return
        _LOGGER.debug('self._state=%s', self._state)
        if self.type == SENSOR_TYPE_STATUS:
            if self._state['state'] == 1:
                if self._state['details']['isCharging']:
                    self._status_state = 'Charging'
                elif (self._state['details']['isDocked'] and
                      not self._state['details']['isCharging']):
                    self._status_state = 'Docked'
                else:
                    self._status_state = 'Stopped'
            elif self._state['state'] == 2:
                if ALERTS.get(self._state['error']) is None:
                    self._status_state = (
                        MODE.get(self._state['cleaning']['mode'])
                        + ' ' + ACTION.get(self._state['action']))
                else:
                    self._status_state = ALERTS.get(self._state['error'])
            elif self._state['state'] == 3:
                self._status_state = 'Paused'
            elif self._state['state'] == 4:
                self._status_state = ERRORS.get(self._state['error'])
        if self.type == SENSOR_TYPE_BATTERY:
            self._battery_state = self._state['details']['charge']
        if self._mapdata is None:
            return
        self.clean_time_start = (
            (self._mapdata[self.robot.serial]['maps'][0]['start_at']
             .strip('Z'))
            .replace('T', ' '))
        self.clean_time_stop = (
            (self._mapdata[self.robot.serial]['maps'][0]['end_at'].strip('Z'))
            .replace('T', ' '))
        self.clean_area = (
            self._mapdata[self.robot.serial]['maps'][0]['cleaned_area'])
        self.clean_suspension_charge_count = (
            self._mapdata[self.robot.serial]['maps'][0]
            ['suspended_cleaning_charging_count'])
        self.clean_suspension_time = (
            self._mapdata[self.robot.serial]['maps'][0]
            ['time_in_suspended_cleaning'])
        self.clean_battery_start = (
            self._mapdata[self.robot.serial]['maps'][0]['run_charge_at_start'])
        self.clean_battery_end = (
            self._mapdata[self.robot.serial]['maps'][0]['run_charge_at_end'])

    @property
    def unit_of_measurement(self):
        """Return unit for the sensor."""
        if self.type == SENSOR_TYPE_BATTERY:
            return '%'

    @property
    def available(self):
        """Return True if sensor data is available."""
        if not self._state:
            return False
        else:
            return True

    @property
    def state(self):
        """Return the sensor state."""
        if self.type == SENSOR_TYPE_STATUS:
            return self._status_state
        if self.type == SENSOR_TYPE_BATTERY:
            return self._battery_state

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._robot_name

    @property
    def device_state_attributes(self):
        """Return the device specific attributes."""
        data = {}
        if self.type is SENSOR_TYPE_STATUS:
            if self.clean_time_start:
                data[ATTR_CLEAN_START] = self.clean_time_start
            if self.clean_time_stop:
                data[ATTR_CLEAN_STOP] = self.clean_time_stop
            if self.clean_area:
                data[ATTR_CLEAN_AREA] = self.clean_area
            if self.clean_suspension_charge_count:
                data[ATTR_CLEAN_SUSP_COUNT] = (
                    self.clean_suspension_charge_count)
            if self.clean_suspension_time:
                data[ATTR_CLEAN_SUSP_TIME] = self.clean_suspension_time
            if self.clean_battery_start:
                data[ATTR_CLEAN_BATTERY_START] = self.clean_battery_start
            if self.clean_battery_end:
                data[ATTR_CLEAN_BATTERY_END] = self.clean_battery_end
        return data
