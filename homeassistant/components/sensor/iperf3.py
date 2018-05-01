"""
Support for Iperf3 network measurement tool.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.iperf3/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.components.sensor import DOMAIN, PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_MONITORED_CONDITIONS, STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import slugify
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import track_time_change
from homeassistant.helpers.restore_state import async_get_last_state
import homeassistant.util.dt as dt_util

REQUIREMENTS = ['iperf3==0.1.10']

_LOGGER = logging.getLogger(__name__)

ATTR_PROTOCOL = 'Protocol'
ATTR_REMOTE_HOST = 'Remote Server'
ATTR_REMOTE_PORT = 'Remote Port'
ATTR_TEST_STATUS = 'Test Status'
ATTR_VERSION = 'Version'

CONF_ATTRIBUTION = 'Data retrieved using Iperf3'
CONF_SECOND = 'second'
CONF_MINUTE = 'minute'
CONF_HOUR = 'hour'
CONF_DAY = 'day'
CONF_MANUAL = 'manual'
CONF_DURATION = 'duration'
CONF_SERVER = 'server'
CONF_PORT = 'port'

DEFAULT_DURATION = 10
DEFAULT_PORT = 5201

ICON = 'mdi:speedometer'

SENSOR_TYPES = {
    'download': ['Download', 'Mbit/s'],
    'upload': ['Upload', 'Mbit/s'],
}


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MONITORED_CONDITIONS):
        vol.All(cv.ensure_list, [vol.In(list(SENSOR_TYPES))]),
    vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Required(CONF_SERVER): cv.string,
    vol.Optional(CONF_DURATION, default=DEFAULT_DURATION): vol.Range(5, 10),
    vol.Optional(CONF_SECOND, default=[0]):
        vol.All(cv.ensure_list, [vol.All(vol.Coerce(int), vol.Range(0, 59))]),
    vol.Optional(CONF_MINUTE, default=[0]):
        vol.All(cv.ensure_list, [vol.All(vol.Coerce(int), vol.Range(0, 59))]),
    vol.Optional(CONF_HOUR):
        vol.All(cv.ensure_list, [vol.All(vol.Coerce(int), vol.Range(0, 23))]),
    vol.Optional(CONF_DAY):
        vol.All(cv.ensure_list, [vol.All(vol.Coerce(int), vol.Range(1, 31))]),
    vol.Optional(CONF_MANUAL, default=False): cv.boolean,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Iperf3 sensor."""
    data = Iperf3Data(hass, config)

    dev = []
    for sensor in config[CONF_MONITORED_CONDITIONS]:
        dev.append(Iperf3Sensor(data, sensor))

    add_devices(dev)

    def update(call=None):
        """Update service for manual updates."""
        data.update(dt_util.now())
        for sensor in dev:
            sensor.update()

    for sensor in dev:
        hass.services.register(DOMAIN, sensor.service_name, update)


class Iperf3Sensor(Entity):
    """A Iperf3 sensor implementation."""

    def __init__(self, iperf3_data, sensor_type):
        """Initialize the sensor."""
        self._name = \
            "{} {}".format(SENSOR_TYPES[sensor_type][0], iperf3_data.server)
        self._state = None
        self._sensor_type = sensor_type
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self.iperf3_client = iperf3_data

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def service_name(self):
        """Return the service name of the sensor."""
        return slugify("{} {}".format(
            'update_iperf3', self.iperf3_client.server))

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self.iperf3_client.data is not None and \
           self.iperf3_client.attrs is not None:
            return self.iperf3_client.attrs

    def update(self):
        """Get the latest data and update the states."""
        data = self.iperf3_client.data
        if data is None:
            return

        if self._sensor_type == 'download':
            self._state = data['download']
        elif self._sensor_type == 'upload':
            self._state = data['upload']

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Handle entity which will be added."""
        state = yield from async_get_last_state(self.hass, self.entity_id)
        if not state:
            return
        self._state = state.state

    @property
    def icon(self):
        """Return icon."""
        return ICON


class Iperf3Data(object):
    """Iperf3 data object."""

    def __init__(self, hass, config):
        """Initialize the data object."""
        self.data = None
        self.attrs = None
        self._server = config.get(CONF_SERVER)
        self._port = config.get(CONF_PORT)
        self._duration = config.get(CONF_DURATION)

        if not config.get(CONF_MANUAL):
            track_time_change(
                hass, self.update, second=config.get(CONF_SECOND),
                minute=config.get(CONF_MINUTE), hour=config.get(CONF_HOUR),
                day=config.get(CONF_DAY))

    @property
    def server(self):
        """Return server attribute."""
        return self._server

    def update(self, now):
        """Get the latest data using Iperf3."""
        import iperf3

        _LOGGER.info("Iperf3 sensor: Connecting to %s:%s",
                     self._server, self._port)

        try:
            client = iperf3.Client()
            client.duration = self._duration
            client.server_hostname = self._server
            client.port = self._port
            client.verbose = False
            result = client.run()

            if result:
                if result.error is not None:

                    # if fails set to STATE_UNKNOWN
                    _LOGGER.error("Iperf3 sensor error: %s", result.error)

                    self.data = {
                        'download': STATE_UNKNOWN,
                        'upload': STATE_UNKNOWN,
                    }

                    self.attrs = {
                        ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
                        ATTR_PROTOCOL: STATE_UNKNOWN,
                        ATTR_REMOTE_HOST: STATE_UNKNOWN,
                        ATTR_REMOTE_PORT: STATE_UNKNOWN,
                        ATTR_VERSION: STATE_UNKNOWN,
                        ATTR_TEST_STATUS: result.error,
                    }

                else:

                    self.data = {
                        'download': result.received_Mbps,
                        'upload': result.sent_Mbps,
                    }

                    self.attrs = {
                        ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
                        ATTR_PROTOCOL: result.protocol,
                        ATTR_REMOTE_HOST: result.remote_host,
                        ATTR_REMOTE_PORT: result.remote_port,
                        ATTR_VERSION: result.version,
                        ATTR_TEST_STATUS: 'OK',
                    }

        except (OSError, AttributeError) as error:
            _LOGGER.error("Iperf3 sensor error: %s", error)
