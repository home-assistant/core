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
    'active_power': ['Active Power', 'mdi:power-plug', 'local', 'W'],
    'current': ['Current', 'mdi:gauge', 'local', 'Amps'],
    'voltage': ['Voltage', 'mdi:gauge', 'local', 'V'],
    'active_cosfi': ['Power Factor', 'mdi:gauge', 'local', '%'],
    'solar_today': ['Solar Today', 'mdi:white-balance-sunny', 'remote', 'kW'],
    'power_today': ['Power Today', 'mdi:power-plug', 'remote', 'kW']
}

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Smappee sensor."""
    smappee = hass.data[DATA_SMAPPEE]

    dev = []
    if smappee.is_remote_active:
        for sensor in SENSOR_TYPES:
            if 'remote' in SENSOR_TYPES[sensor]:
                for location_id in smappee.locations.keys():
                    dev.append(SmappeeSensor(smappee, location_id, sensor))

    if smappee.is_local_active:
        for sensor in SENSOR_TYPES:
            if 'local' in SENSOR_TYPES[sensor]:
                if smappee.is_remote_active:
                    for location_id in smappee.locations.keys():
                        dev.append(SmappeeSensor(smappee, location_id, sensor))
                else:
                    dev.append(SmappeeSensor(smappee, None, sensor))
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
        if self._location_id:
            location_name = self._smappee.locations[self._location_id]
        else:
            location_name = 'Local'

        return "{} {} {}".format(SENSOR_PREFIX,
                                 location_name,
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
        if self._location_id:
            attr['Location Id'] = self._location_id
            attr['Location Name'] = self._smappee.locations[self._location_id]
        attr['Last Update'] = self._timestamp
        return attr

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Get the latest data from Smappee and update the state."""
        if self._sensor == 'alwaysOn':
            data = self._smappee.get_consumption(
                self._location_id, aggregation=1, delta=30)
            _LOGGER.debug("%s %s", self._sensor, data)
            if data:
                consumption = data.get('consumptions')[-1]
                self._timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._state = consumption.get(self._sensor)
        elif self._sensor == 'solar_today':
            data = self._smappee.get_consumption(
                self._location_id, aggregation=3, delta=1440)
            _LOGGER.debug("%s %s", self._sensor, data)
            if data:
                consumption = data.get('consumptions')[-1]
                self._timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._state = round(consumption.get('solar') / 1000, 2)
        elif self._sensor == 'power_today':
            data = self._smappee.get_consumption(
                self._location_id, aggregation=3, delta=1440)
            _LOGGER.debug("%s %s", self._sensor, data)
            if data:
                consumption = data.get('consumptions')[-1]
                self._timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._state = round(consumption.get('consumption') / 1000, 2)
        elif self._sensor == 'active_cosfi':
            cosfi = self._smappee.active_cosfi()
            _LOGGER.debug("%s %s", self._sensor, cosfi)
            if cosfi:
                self._timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._state = round(cosfi, 2)
        elif self._sensor == 'current':
            current = self._smappee.active_current()
            _LOGGER.debug("%s %s", self._sensor, current)
            if current:
                self._timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._state = round(current, 2)
        elif self._sensor == 'voltage':
            voltage = self._smappee.active_voltage()
            _LOGGER.debug("%s %s", self._sensor, voltage)
            if voltage:
                self._timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self._state = round(voltage, 3)
        elif self._sensor == 'active_power':
            data = self._smappee.load_instantaneous()
            _LOGGER.debug("%s %s", self._sensor, data)
            if data:
                value1 = [float(i['value']) for i in data
                          if i['key'].endswith('phase0ActivePower')]
                value2 = [float(i['value']) for i in data
                          if i['key'].endswith('phase1ActivePower')]
                value3 = [float(i['value']) for i in data
                          if i['key'].endswith('phase2ActivePower')]
                active_power = sum(value1 + value2 + value3) / 1000
                self._state = round(active_power, 2)
                self._timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        elif self._sensor == 'solar':
            data = self._smappee.load_instantaneous()
            _LOGGER.debug("%s %s", self._sensor, data)
            if data:
                value1 = [float(i['value']) for i in data
                          if i['key'].endswith('phase3ActivePower')]
                value2 = [float(i['value']) for i in data
                          if i['key'].endswith('phase4ActivePower')]
                value3 = [float(i['value']) for i in data
                          if i['key'].endswith('phase5ActivePower')]
                power = sum(value1 + value2 + value3) / 1000
                self._state = round(power, 2)
                self._timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            return None
