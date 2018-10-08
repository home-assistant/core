"""
Support for Speedtest.net.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.speedtest/
"""
import logging

import voluptuous as vol

from homeassistant.components.sensor import DOMAIN, PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION, CONF_MONITORED_CONDITIONS
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_time_change
from homeassistant.helpers.restore_state import async_get_last_state
import homeassistant.util.dt as dt_util

REQUIREMENTS = ['speedtest-cli==2.0.2']

_LOGGER = logging.getLogger(__name__)

ATTR_BYTES_RECEIVED = 'bytes_received'
ATTR_BYTES_SENT = 'bytes_sent'
ATTR_SERVER_COUNTRY = 'server_country'
ATTR_SERVER_HOST = 'server_host'
ATTR_SERVER_ID = 'server_id'
ATTR_SERVER_LATENCY = 'latency'
ATTR_SERVER_NAME = 'server_name'

CONF_ATTRIBUTION = "Data retrieved from Speedtest by Ookla"
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
    vol.Optional(CONF_DAY):
        vol.All(cv.ensure_list, [vol.All(vol.Coerce(int), vol.Range(1, 31))]),
    vol.Optional(CONF_HOUR):
        vol.All(cv.ensure_list, [vol.All(vol.Coerce(int), vol.Range(0, 23))]),
    vol.Optional(CONF_MANUAL, default=False): cv.boolean,
    vol.Optional(CONF_MINUTE, default=[0]):
        vol.All(cv.ensure_list, [vol.All(vol.Coerce(int), vol.Range(0, 59))]),
    vol.Optional(CONF_SECOND, default=[0]):
        vol.All(cv.ensure_list, [vol.All(vol.Coerce(int), vol.Range(0, 59))]),
    vol.Optional(CONF_SERVER_ID): cv.positive_int,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Speedtest sensor."""
    data = SpeedtestData(hass, config)

    dev = []
    for sensor in config[CONF_MONITORED_CONDITIONS]:
        dev.append(SpeedtestSensor(data, sensor))

    add_entities(dev)

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
        self._data = None
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

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._data is not None:
            return {
                ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
                ATTR_BYTES_RECEIVED: self._data['bytes_received'],
                ATTR_BYTES_SENT: self._data['bytes_sent'],
                ATTR_SERVER_COUNTRY: self._data['server']['country'],
                ATTR_SERVER_ID: self._data['server']['id'],
                ATTR_SERVER_LATENCY: self._data['server']['latency'],
                ATTR_SERVER_NAME: self._data['server']['name'],
            }

    def update(self):
        """Get the latest data and update the states."""
        self._data = self.speedtest_client.data
        if self._data is None:
            return

        if self.type == 'ping':
            self._state = self._data['ping']
        elif self.type == 'download':
            self._state = round(self._data['download'] / 10**6, 2)
        elif self.type == 'upload':
            self._state = round(self._data['upload'] / 10**6, 2)

    async def async_added_to_hass(self):
        """Handle all entity which are about to be added."""
        state = await async_get_last_state(self.hass, self.entity_id)
        if not state:
            return
        self._state = state.state


class SpeedtestData:
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
        _LOGGER.debug("Executing speedtest...")

        servers = [] if self._server_id is None else [self._server_id]

        speed = speedtest.Speedtest()
        speed.get_servers(servers)
        speed.get_best_server()
        speed.download()
        speed.upload()

        self.data = speed.results.dict()
