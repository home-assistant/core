"""Support gathering system information of hosts which are running glances."""
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PORT, CONF_USERNAME, CONF_PASSWORD, CONF_SSL,
    CONF_VERIFY_SSL, CONF_RESOURCES, STATE_UNAVAILABLE, TEMP_CELSIUS)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

CONF_VERSION = 'version'

DEFAULT_HOST = 'localhost'
DEFAULT_NAME = 'Glances'
DEFAULT_PORT = '61208'
DEFAULT_VERSION = 2

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=1)

SENSOR_TYPES = {
    'disk_use_percent': ['Disk used', '%', 'mdi:harddisk'],
    'disk_use': ['Disk used', 'GiB', 'mdi:harddisk'],
    'disk_free': ['Disk free', 'GiB', 'mdi:harddisk'],
    'memory_use_percent': ['RAM used', '%', 'mdi:memory'],
    'memory_use': ['RAM used', 'MiB', 'mdi:memory'],
    'memory_free': ['RAM free', 'MiB', 'mdi:memory'],
    'swap_use_percent': ['Swap used', '%', 'mdi:memory'],
    'swap_use': ['Swap used', 'GiB', 'mdi:memory'],
    'swap_free': ['Swap free', 'GiB', 'mdi:memory'],
    'processor_load': ['CPU load', '15 min', 'mdi:memory'],
    'process_running': ['Running', 'Count', 'mdi:memory'],
    'process_total': ['Total', 'Count', 'mdi:memory'],
    'process_thread': ['Thread', 'Count', 'mdi:memory'],
    'process_sleeping': ['Sleeping', 'Count', 'mdi:memory'],
    'cpu_use_percent': ['CPU used', '%', 'mdi:memory'],
    'cpu_temp': ['CPU Temp', TEMP_CELSIUS, 'mdi:thermometer'],
    'docker_active': ['Containers active', '', 'mdi:docker'],
    'docker_cpu_use': ['Containers CPU used', '%', 'mdi:docker'],
    'docker_memory_use': ['Containers RAM used', 'MiB', 'mdi:docker'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_USERNAME): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_SSL, default=False): cv.boolean,
    vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
    vol.Optional(CONF_RESOURCES, default=['disk_use']):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_VERSION, default=DEFAULT_VERSION): vol.In([2, 3]),
})


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the Glances sensors."""
    from glances_api import Glances

    name = config[CONF_NAME]
    host = config[CONF_HOST]
    port = config[CONF_PORT]
    version = config[CONF_VERSION]
    var_conf = config[CONF_RESOURCES]
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    ssl = config[CONF_SSL]
    verify_ssl = config[CONF_VERIFY_SSL]

    session = async_get_clientsession(hass, verify_ssl)
    glances = GlancesData(
        Glances(hass.loop, session, host=host, port=port, version=version,
                username=username, password=password, ssl=ssl))

    await glances.async_update()

    if glances.api.data is None:
        raise PlatformNotReady

    dev = []
    for resource in var_conf:
        dev.append(GlancesSensor(glances, name, resource))

    async_add_entities(dev, True)


class GlancesSensor(Entity):
    """Implementation of a Glances sensor."""

    def __init__(self, glances, name, sensor_type):
        """Initialize the sensor."""
        self.glances = glances
        self._name = name
        self.type = sensor_type
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self._name, SENSOR_TYPES[self.type][0])

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return SENSOR_TYPES[self.type][2]

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def available(self):
        """Could the device be accessed during the last update call."""
        return self.glances.available

    @property
    def state(self):
        """Return the state of the resources."""
        return self._state

    async def async_update(self):
        """Get the latest data from REST API."""
        await self.glances.async_update()
        value = self.glances.api.data

        if value is not None:
            if self.type == 'disk_use_percent':
                self._state = value['fs'][0]['percent']
            elif self.type == 'disk_use':
                self._state = round(value['fs'][0]['used'] / 1024**3, 1)
            elif self.type == 'disk_free':
                try:
                    self._state = round(value['fs'][0]['free'] / 1024**3, 1)
                except KeyError:
                    self._state = round((value['fs'][0]['size'] -
                                         value['fs'][0]['used']) / 1024**3, 1)
            elif self.type == 'memory_use_percent':
                self._state = value['mem']['percent']
            elif self.type == 'memory_use':
                self._state = round(value['mem']['used'] / 1024**2, 1)
            elif self.type == 'memory_free':
                self._state = round(value['mem']['free'] / 1024**2, 1)
            elif self.type == 'swap_use_percent':
                self._state = value['memswap']['percent']
            elif self.type == 'swap_use':
                self._state = round(value['memswap']['used'] / 1024**3, 1)
            elif self.type == 'swap_free':
                self._state = round(value['memswap']['free'] / 1024**3, 1)
            elif self.type == 'processor_load':
                # Windows systems don't provide load details
                try:
                    self._state = value['load']['min15']
                except KeyError:
                    self._state = value['cpu']['total']
            elif self.type == 'process_running':
                self._state = value['processcount']['running']
            elif self.type == 'process_total':
                self._state = value['processcount']['total']
            elif self.type == 'process_thread':
                self._state = value['processcount']['thread']
            elif self.type == 'process_sleeping':
                self._state = value['processcount']['sleeping']
            elif self.type == 'cpu_use_percent':
                self._state = value['quicklook']['cpu']
            elif self.type == 'cpu_temp':
                for sensor in value['sensors']:
                    if sensor['label'] in ['CPU', "Package id 0",
                                           "Physical id 0", "cpu-thermal 1",
                                           "exynos-therm 1", "soc_thermal 1"]:
                        self._state = sensor['value']
            elif self.type == 'docker_active':
                count = 0
                try:
                    for container in value['docker']['containers']:
                        if container['Status'] == 'running' or \
                                'Up' in container['Status']:
                            count += 1
                    self._state = count
                except KeyError:
                    self._state = count
            elif self.type == 'docker_cpu_use':
                cpu_use = 0.0
                try:
                    for container in value['docker']['containers']:
                        if container['Status'] == 'running' or \
                                'Up' in container['Status']:
                            cpu_use += container['cpu']['total']
                        self._state = round(cpu_use, 1)
                except KeyError:
                    self._state = STATE_UNAVAILABLE
            elif self.type == 'docker_memory_use':
                mem_use = 0.0
                try:
                    for container in value['docker']['containers']:
                        if container['Status'] == 'running' or \
                                'Up' in container['Status']:
                            mem_use += container['memory']['usage']
                        self._state = round(mem_use / 1024**2, 1)
                except KeyError:
                    self._state = STATE_UNAVAILABLE


class GlancesData:
    """The class for handling the data retrieval."""

    def __init__(self, api):
        """Initialize the data object."""
        self.api = api
        self.available = True

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the latest data from the Glances REST API."""
        from glances_api.exceptions import GlancesApiError

        try:
            await self.api.get_data()
            self.available = True
        except GlancesApiError:
            _LOGGER.error("Unable to fetch data from Glances")
            self.available = False
