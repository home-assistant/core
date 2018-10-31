"""
@ Author      : Gerben Jongerius
@ Date        : 04/29/2018
@ Description : Youless Sensor - Monitor power consumption. This component will add the following sensors
                   - Current power consumption (in W)
                   - Current tick count, since the Youless meter started running (in W)
"""
import json
import logging
from datetime import timedelta
from urllib.request import urlopen

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_MONITORED_VARIABLES
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

SENSOR_POWER = 'pwr'
SENSOR_POWER_NET = 'net'
SENSOR_P_HIGH = 'p2'
SENSOR_P_LOW = 'p1'
SENSOR_GAS = 'gas'

DOMAIN = 'youless'
CONF_HOST = "host"
CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_HOST): cv.string,
        vol.Optional(CONF_MONITORED_VARIABLES,
                     default=[SENSOR_POWER, SENSOR_POWER_NET]): vol.All(
            cv.ensure_list, vol.Length(min=1),
            [vol.In([SENSOR_POWER, SENSOR_POWER_NET, SENSOR_P_LOW,
                     SENSOR_P_HIGH, SENSOR_GAS])])
    })
}, extra=vol.ALLOW_EXTRA)

SENSOR_PREFIX = 'youless_'
_LOGGER = logging.getLogger(__name__)

SENSOR_TYPES = {
    SENSOR_POWER: ['Usage', 'usage', 'W', 'mdi:flash'],
    SENSOR_POWER_NET: ['Power', 'meter', 'W', 'mdi:gauge'],
    SENSOR_P_LOW: ['Power Low', 'meter_low', 'kWh', 'mdi:flash'],
    SENSOR_P_HIGH: ['Power High', 'meter_high', 'kWh', 'mdi:flash'],
    SENSOR_GAS: ['Gas', 'gas', 'm3', 'mdi:fire']
}


def setup_platform(hass, config, add_devices, discovery_info=None):
    host = config.get(CONF_HOST)
    sensors = config.get(CONF_MONITORED_VARIABLES)
    data_bridge = YoulessDataBridge(host)

    devices = []
    for sensor in sensors:
        sensor_config = SENSOR_TYPES[sensor]
        devices.append(YoulessSensor(data_bridge, sensor_config[0], sensor,
                                     sensor_config[1], sensor_config[2],
                                     sensor_config[3]))

    add_devices(devices)


class YoulessDataBridge(object):

    def __init__(self, host):
        self._url = 'http://' + host + '/e'
        self._data = None

    def data(self):
        return self._data

    @Throttle(timedelta(seconds=1))
    def update(self):
        raw_res = urlopen(self._url)
        self._data = json.loads(raw_res.read().decode('utf-8'))[0]


class YoulessSensor(Entity):

    def __init__(self, data_bridge, name, variable, sensor_id, uom, icon):
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
        return self._name

    @property
    def icon(self):
        return self._icon

    @property
    def unit_of_measurement(self):
        return self._uom

    @property
    def state(self):
        return self._state

    @property
    def state_attributes(self):
        if self._raw is not None:
            return {
                'timestamp': self._raw['tm']
            }

    def update(self):
        self._data_bridge.update()
        self._raw = self._data_bridge.data()
        if self._raw is not None:
            self._state = self._raw[self._property]
