"""
Support for Roomba Connected Vaccums sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.roomba/
"""
import logging
from homeassistant.helpers.entity import Entity
from homeassistant.components.roomba import ROOMBA_ROBOTS

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['roomba']

SENSOR_TYPE_BIN = 'bin'
SENSOR_TYPE_BATTERY = 'battery'
SENSOR_TYPE_POSITION = 'position'
SENSOR_TYPE_STATUS = 'status'

SENSOR_TYPES = {
    SENSOR_TYPE_BATTERY: ['Battery'],
    SENSOR_TYPE_BIN: ['Bin'],
    SENSOR_TYPE_POSITION: ['Position'],
    SENSOR_TYPE_STATUS: ['Status']
}

ATTR_BIN_PRESENT = 'bin_present'
ATTR_BATTERY_CHARGING = 'charging'
ATTR_POSITION_X = 'pos_x'
ATTR_POSITION_Y = 'pos_y'
ATTR_POSITION_THETA = 'pos_theta'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Roomba sensor platform."""
    dev = []
    for roomba_hub in hass.data[ROOMBA_ROBOTS]:
        for type_name in SENSOR_TYPES:
            dev.append(RoombaSensor(hass, roomba_hub, type_name))
    _LOGGER.debug('Adding sensors %s', dev)
    add_devices(dev)


class RoombaSensor(Entity):
    """Roomba Sensor."""

    def __init__(self, hass, roomba_hub, sensor_type):
        """Initialize the Roomba Connected sensor."""
        self.roomba_hub = roomba_hub
        self.sensor_type = sensor_type
        self._state = None
        self._attrs = None
        if self.sensor_type == SENSOR_TYPE_BIN:
            self._sensor_name = 'Roomba Bin'
        elif self.sensor_type == SENSOR_TYPE_BATTERY:
            self._sensor_name = 'Roomba Battery'
        elif self.sensor_type == SENSOR_TYPE_POSITION:
            self._sensor_name = 'Roomba Position'
        elif self.sensor_type == SENSOR_TYPE_STATUS:
            self._sensor_name = 'Roomba State'
        self.__set_sensor_state_from_hub()

    def __set_sensor_state_from_hub(self):
        roomba_data = self.roomba_hub.data
        roomba_name = roomba_data['state'].get('name', 'Roomba')
        if self.sensor_type == SENSOR_TYPE_BIN:
            bin_data = roomba_data['state'].get('bin', {})
            self._state = bin_data.get('full', None)
            self._attrs = {ATTR_BIN_PRESENT: bin_data.get('present', None)}
            if roomba_name:
                self._sensor_name = '{} Bin'.format(roomba_name)
        elif self.sensor_type == SENSOR_TYPE_BATTERY:
            clean_mission_status = \
                roomba_data['state'].get('cleanMissionStatus', {})
            phase_data = clean_mission_status.get('phase', None)
            self._state = \
                roomba_data['state'].get('batPct', None)
            self._attrs = {
                ATTR_BATTERY_CHARGING: phase_data == 'charge' \
                    if phase_data else None
            }
            if roomba_name:
                self._sensor_name = '{} Battery'.format(roomba_name)
        elif self.sensor_type == SENSOR_TYPE_POSITION:
            position_data = roomba_data['state'].get('pose', None)
            pos_x = position_data.get('point', {}).get('x', None)
            pos_y = position_data.get('point', {}).get('y', None)
            theta = position_data.get('theta', None)
            if pos_x and pos_y and theta:
                self._state = '({},{},{})'.format(pos_x, pos_y, theta)
            else:
                self._state = None
            self._attrs = {
                ATTR_POSITION_X: pos_x,
                ATTR_POSITION_Y: pos_y,
                ATTR_POSITION_THETA: theta
            }
            if roomba_name:
                self._sensor_name = '{} Position'.format(roomba_name)
        elif self.sensor_type == SENSOR_TYPE_STATUS:
            self._state = roomba_data['status']
            if roomba_name:
                self._sensor_name = '{} Status'.format(roomba_name)
        _LOGGER.debug('%s sensor state: %s', self.sensor_type, self._state)

    def update(self):
        """Update the properties of sensor."""
        _LOGGER.debug('Update of Roomba %s sensor', self.sensor_type)
        self.roomba_hub.update()
        self.__set_sensor_state_from_hub()

    @property
    def unit_of_measurement(self):
        """Return unit for the sensor."""
        if self.sensor_type == SENSOR_TYPE_BATTERY:
            return '%'

    @property
    def available(self):
        """Return True if sensor data is available."""
        return self._state is not None

    @property
    def state(self):
        """Return the sensor state."""
        return self._state

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._sensor_name

    @property
    def device_state_attributes(self):
        """Return the device specific attributes."""
        return self._attrs
