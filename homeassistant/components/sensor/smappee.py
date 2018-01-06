"""
Support for monitoring a Smappee energy sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.smappee/
"""
import logging
from datetime import datetime, timedelta

from homeassistant.components.smappee import DATA_SMAPPEE
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

DEPENDENCIES = ['smappee']

_LOGGER = logging.getLogger(__name__)

SENSOR_PREFIX = 'Smappee'
SENSOR_TYPES = {
    'solar': ['Solar', 'mdi:white-balance-sunny', 'local', 'W'],
    'alwaysOn': ['Always On', 'mdi:gauge', 'remote', 'W'],
    'current': ['Current', 'mdi:power-plug', 'local', 'W'],
    'solar_today': ['Solar Today', 'mdi:white-balance-sunny', 'remote', 'kW'],
    'current_today': ['Current Today', 'mdi:power-plug', 'remote', 'kW']
}

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Smappee sensor."""
    smappee = hass.data[DATA_SMAPPEE]

    dev = []
    for location_id, location_name in smappee.locations.items():
        for sensor in SENSOR_TYPES:
            dev.append(SmappeeSensor(smappee, location_id, sensor))

    add_devices(dev)


class SmappeeSensor(Entity):
    """Implementation of a Smappee sensor."""

    def __init__(self, smappee, location_id, sensor):
        """Initialize the sensor."""
        self._smappee = smappee
        self._location_id = location_id
        self._sensor = sensor
        self.data = None
        self._state = None
        self._timestamp = None
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return "{} {} {}".format(SENSOR_PREFIX,
                                 self._smappee.locations[self._location_id],
                                 SENSOR_TYPES[self._sensor][0])

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return SENSOR_TYPES[self._sensor][1]

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return SENSOR_TYPES[self._sensor][3]

    @property
    def device_state_attributes(self):
        """Return the state attributes of the device."""
        attr = {}
        attr['Location Id'] = self._location_id
        attr['Location Name'] = self._smappee.locations[self._location_id]
        attr['Last Update'] = self._timestamp
        return attr

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from Smappee and update the state."""
        if SENSOR_TYPES[self._sensor][0] == 'Always On':
            data = self._smappee.get_consumption(
                    self._location_id, aggregation=1, delta=30)
            consumption = data.get('consumptions')[-1]
            self._timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._state = consumption.get(self._sensor)
        elif SENSOR_TYPES[self._sensor][0] == 'Solar Today':
            data = self._smappee.get_consumption(
                    self._location_id, aggregation=3, delta=1440)
            consumption = data.get('consumptions')[-1]
            self._timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._state = round(consumption.get('solar') / 1000, 2)
        elif SENSOR_TYPES[self._sensor][0] == 'Current Today':
            data = self._smappee.get_consumption(
                    self._location_id, aggregation=3, delta=1440)
            consumption = data.get('consumptions')[-1]
            self._timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._state = round(consumption.get('consumption') / 1000, 2)
        elif SENSOR_TYPES[self._sensor][0] is 'Current':
            data = self._smappee.load_instantaneous()
            value1 = [float(i['value']) for i in data
                      if i['key'].endswith('phase0ActivePower')]
            value2 = [float(i['value']) for i in data
                      if i['key'].endswith('phase1ActivePower')]
            value3 = [float(i['value']) for i in data
                      if i['key'].endswith('phase2ActivePower')]
            current = sum(value1 + value2 + value3) / 1000
            self._state = round(current, 2)
            self._timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        elif SENSOR_TYPES[self._sensor][0] is 'Solar':
            data = self._smappee.load_instantaneous()
            value1 = [float(i['value']) for i in data
                      if i['key'].endswith('phase3ActivePower')]
            value2 = [float(i['value']) for i in data
                      if i['key'].endswith('phase4ActivePower')]
            value3 = [float(i['value']) for i in data
                      if i['key'].endswith('phase5ActivePower')]
            current = sum(value1 + value2 + value3) / 1000
            self._state = round(current, 2)
            self._timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            return None
