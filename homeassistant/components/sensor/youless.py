"""
Support for YouLess device.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.youless/
"""
import json
from datetime import timedelta
from urllib.request import urlopen

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_HOST, CONF_MONITORED_CONDITIONS
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

SENSOR_POWER = 'pwr'
SENSOR_POWER_NET = 'net'
SENSOR_P_LOW = 'p1'
SENSOR_P_HIGH = 'p2'
SENSOR_DELIVERY_LOW = 'n1'
SENSOR_DELIVERY_HIGH = 'n2'
SENSOR_METER_EXTRA = 'cs0'
SENSOR_USAGE_EXTRA = 'ps0'
SENSOR_GAS = 'gas'

SENSOR_TYPES = {
    SENSOR_POWER: ['Usage', 'usage', 'W', 'mdi:flash'],
    SENSOR_POWER_NET: ['Power', 'meter', 'W', 'mdi:gauge'],
    SENSOR_P_LOW: ['Power Low', 'meter_low', 'kWh', 'mdi:flash'],
    SENSOR_P_HIGH: ['Power High', 'meter_high', 'kWh', 'mdi:flash'],
    SENSOR_DELIVERY_LOW: ['Power Delivery Low', 'delivery_low', 'kWh',
                          'mdi:gauge'],
    SENSOR_DELIVERY_HIGH: ['Power Delivery High', 'delivery_high', 'kWh',
                           'mdi:gauge'],
    SENSOR_METER_EXTRA: ['Power Meter Extra', 'meter_extra', 'kWh',
                         'mdi:gauge'],
    SENSOR_USAGE_EXTRA: ['Power usage Extra', 'current_usage_extra', 'W',
                         'mdi:flash'],
    SENSOR_GAS: ['Gas', 'gas', 'm3', 'mdi:fire']
}

CONFIG_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HOST): cv.string,
    vol.Optional(CONF_MONITORED_CONDITIONS,
                 default=[SENSOR_POWER, SENSOR_POWER_NET]): vol.All(
                     cv.ensure_list, vol.Length(min=1),
                     [vol.In(SENSOR_TYPES)])
})

SENSOR_PREFIX = 'youless_'


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the platform based on the configuration."""
    host = config.get(CONF_HOST)
    sensors = config.get(CONF_MONITORED_CONDITIONS)
    data_bridge = YoulessDataBridge(host)

    devices = []
    for sensor in sensors:
        sensor_config = SENSOR_TYPES[sensor]
        devices.append(YoulessSensor(data_bridge, sensor_config[0], sensor,
                                     sensor_config[1], sensor_config[2],
                                     sensor_config[3]))

    add_devices(devices)


class YoulessDataBridge:
    """A helper class responsible for fetching data."""

    def __init__(self, host):
        """Initialize the helper class."""
        self._url = 'http://' + host + '/e'
        self._data = None

    def data(self):
        """Return the values obtained during the last fetch."""
        return self._data

    @Throttle(timedelta(seconds=1))
    def update(self):
        """Get  the inner values by calling the YouLess API."""
        raw_res = urlopen(self._url)
        self._data = json.loads(raw_res.read().decode('utf-8'))[0]


class YoulessSensor(Entity):
    """The sensor implementation for YouLess."""

    def __init__(self, data_bridge, name, variable, sensor_id, uom, icon):
        """Set up the sensor."""
        self._state = None
        self._name = name
        self._property = variable
        self._icon = icon
        self._uom = uom
        self._data_bridge = data_bridge
        self.entity_id = 'sensor.' + SENSOR_PREFIX + sensor_id
        self._raw = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Return the icon of the sensor depending on the type selected."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the unit of measure for the created sensor."""
        return self._uom

    @property
    def state(self):
        """Return the value stored during the fetching of the data."""
        return self._state

    @property
    def state_attributes(self):
        """Return the timestamp that the last measurement was done."""
        if self._raw is not None:
            return {
                'timestamp': self._raw['tm']
            }

    def update(self):
        """Update the internal state of the sensor using the data fetcher."""
        self._data_bridge.update()
        self._raw = self._data_bridge.data()
        if self._raw is not None:
            self._state = self._raw[self._property]
