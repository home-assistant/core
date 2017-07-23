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

SENSOR_TYPE_BATTERY = 'battery'
SENSOR_TYPE_POSITION = 'position'
SENSOR_TYPE_STATUS = 'status'

SENSOR_TYPES = {
    SENSOR_TYPE_BATTERY: ['Battery'],
    SENSOR_TYPE_POSITION: ['Position'],
    SENSOR_TYPE_STATUS: ['Status']
}


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
        if self.sensor_type == SENSOR_TYPE_BATTERY:
            self._sensor_name = 'Roomba Battery'
        elif self.sensor_type == SENSOR_TYPE_POSITION:
            self._sensor_name = 'Roomba Position'
        elif self.sensor_type == SENSOR_TYPE_STATUS:
            self._sensor_name = 'Roomba State'
        self.__set_sensor_state_from_hub()

    def __set_sensor_state_from_hub(self):
        roomba_data = self.roomba_hub.data
        roomba_name = roomba_data['state'].get('name', 'Roomba')
        if self.sensor_type == SENSOR_TYPE_BATTERY:
            self._state = \
                roomba_data['state'].get('batPct', None)
            self._sensor_name = '{} Battery'.format(roomba_name)
        elif self.sensor_type == SENSOR_TYPE_POSITION:
            position_data = roomba_data['state'].get('pose', None)
            pos_x = position_data.get('point', []).get('x', None)
            pos_y = position_data.get('point', []).get('y', None)
            theta = position_data.get('theta', None)
            self._state = '({},{},{})'.format(pos_x, pos_y, theta)
            self._sensor_name = '{} Position'.format(roomba_name)
        elif self.sensor_type == SENSOR_TYPE_STATUS:
            self._state = roomba_data['status']
            self._sensor_name = '{} Status'.format(roomba_name)
        _LOGGER.debug('Sensor state: %s', self._state)

    def update(self):
        """Update the properties of sensor."""
        _LOGGER.debug('Update of roomba sensor')
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
        data = {}
        return data
