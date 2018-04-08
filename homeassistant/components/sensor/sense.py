"""
Support for monitoring a Sense energy sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.sense/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_EMAIL, CONF_PASSWORD,
                                 CONF_MONITORED_CONDITIONS)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['sense_energy==0.3.1']

_LOGGER = logging.getLogger(__name__)

ACTIVE_NAME = "Energy"
PRODUCTION_NAME = "Production"
CONSUMPTION_NAME = "Usage"
DEVICES_NAME = "Devices"
DEVICES_NAME_LOWER = DEVICES_NAME.lower()

ACTIVE_TYPE = 'active'


class SensorConfig(object):
    """Data structure holding sensor config."""

    def __init__(self, name, sensor_type):
        """Sensor name and type to pass to API."""
        self.name = name
        self.sensor_type = sensor_type


# Sensor types/ranges
SENSOR_TYPES = {'active': SensorConfig(ACTIVE_NAME, ACTIVE_TYPE),
                'daily': SensorConfig('Daily', 'DAY'),
                'weekly': SensorConfig('Weekly', 'WEEK'),
                'monthly': SensorConfig('Monthly', 'MONTH'),
                'yearly': SensorConfig('Yearly', 'YEAR')}

# Production/consumption variants
SENSOR_VARIANTS = [PRODUCTION_NAME.lower(), CONSUMPTION_NAME.lower()]

# Valid sensors for configuration
VALID_SENSORS = ['%s_%s' % (typ, var)
                 for typ in SENSOR_TYPES
                 for var in SENSOR_VARIANTS]
VALID_SENSORS.append(DEVICES_NAME_LOWER)

CONSUMPTION_ICON = 'mdi:flash'
PRODUCTION_ICON = 'mdi:white-balance-sunny'

DEVICE_ICON_TO_MDI_MAP = {
    'alwayson': 'mdi:sync',
    'cup': 'mdi:coffee',
    'fan': 'mdi:fan',
    'fridge': 'mdi:fridge',
    'home': 'mdi:help',
    'lightbulb': 'mdi:lightbulb',
    'microwave': 'mdi:waves',
    'stove': 'mdi:stove',
    'toaster_oven': 'mdi:stove',
    'tv': 'mdi:television',
    'washer': 'mdi:washing-machine'
}


MIN_TIME_BETWEEN_DAILY_UPDATES = timedelta(seconds=300)
MIN_TIME_BETWEEN_REALTIME_UPDATES = timedelta(seconds=30)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_EMAIL): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_MONITORED_CONDITIONS):
        vol.All(cv.ensure_list, vol.Length(min=1), [vol.In(VALID_SENSORS)]),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Sense sensor."""
    from sense_energy import Senseable

    username = config.get(CONF_EMAIL)
    password = config.get(CONF_PASSWORD)

    data = Senseable(username, password)
    realtime_data_wrapper = ThrottledRealtimeData(data)

    @Throttle(MIN_TIME_BETWEEN_DAILY_UPDATES)
    def update_trends():
        """Update the daily power usage."""
        data.update_trend_data()

    def update_active():
        """Update the active power usage."""
        realtime_data_wrapper.update_realtime()

    devices = []
    for sensor in config.get(CONF_MONITORED_CONDITIONS):
        if sensor != DEVICES_NAME_LOWER:
            config_name, prod = sensor.rsplit('_', 1)
            name = SENSOR_TYPES[config_name].name
            sensor_type = SENSOR_TYPES[config_name].sensor_type
            is_production = prod == PRODUCTION_NAME.lower()
            if sensor_type == ACTIVE_TYPE:
                update_call = update_active
            else:
                update_call = update_trends
            devices.append(
                SenseProductionConsumption(data, name, sensor_type,
                                           is_production, update_call))
        else:
            sense_devices = data.get_discovered_device_data()
            devices.extend([SenseDevice(realtime_data_wrapper,
                                        d['name'], d.get('location', ''),
                                        d['icon']) for d in sense_devices])

    add_devices(devices)


class ThrottledRealtimeData():
    """Implementation of throttled Sense realtime data wrapper."""

    def __init__(self, data):
        """Initialize the throttled realtime data wrapper."""
        self._data = data
        self._realtime_data = None

    @property
    def realtime_data(self):
        """Return the last fetched payload of realtime data."""
        self.update_realtime()
        return self._realtime_data

    @Throttle(MIN_TIME_BETWEEN_REALTIME_UPDATES)
    def update_realtime(self):
        """Fetch and store an updated realtime payload."""
        self._realtime_data = self._data.get_realtime()


class SenseProductionConsumption(Entity):
    """Implementation of a Sense energy sensor."""

    def __init__(self, data, name, sensor_type, is_production, update_call):
        """Initialize the sensor."""
        name_type = PRODUCTION_NAME if is_production else CONSUMPTION_NAME
        self._name = "%s %s" % (name, name_type)
        self._data = data
        self._sensor_type = sensor_type
        self.update_sensor = update_call
        self._is_production = is_production
        self._state = None

        if sensor_type == ACTIVE_TYPE:
            self._unit_of_measurement = 'W'
        else:
            self._unit_of_measurement = 'kWh'

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        if self._is_production:
            return PRODUCTION_ICON
        return CONSUMPTION_ICON

    def update(self):
        """Get the latest data, update state."""
        self.update_sensor()

        if self._sensor_type == ACTIVE_TYPE:
            if self._is_production:
                self._state = round(self._data.active_solar_power)
            else:
                self._state = round(self._data.active_power)
        else:
            state = self._data.get_trend(self._sensor_type,
                                         self._is_production)
            self._state = round(state, 1)


class SenseDevice(Entity):
    """Implementation of a Sense detected device."""

    def __init__(self, realtime_data_wrapper, name, location, icon):
        """Initialize the sensor."""
        self._realtime_data_wrapper = realtime_data_wrapper
        self._device_name = name
        if location != '':
            self._device_name = '{} ({})'.format(name, location)
        self._name = '{} Energy Usage'.format(self._device_name)
        self._icon = icon
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def force_update(self):
        """Return if an same sensor value should still count as an update."""
        return True

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return 'W'

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        try:
            icon = DEVICE_ICON_TO_MDI_MAP[self._icon]
        except KeyError:
            icon = CONSUMPTION_ICON
        return icon

    def update(self):
        """Get the latest data, update state."""
        payload = self._realtime_data_wrapper.realtime_data
        if 'devices' not in payload:
            self._state = 0
            return

        for device in payload['devices']:
            if device['name'] == self._device_name:
                self._state = round(device['w'])
                return

        self._state = 0
