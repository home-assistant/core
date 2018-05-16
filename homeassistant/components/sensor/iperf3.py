"""
Support for Iperf3 network measurement tool.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.iperf3/
"""
import asyncio
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import DOMAIN, PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, CONF_MONITORED_CONDITIONS, CONF_HOST, CONF_PORT)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import slugify
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.restore_state import async_get_last_state

REQUIREMENTS = ['iperf3==0.1.10']

_LOGGER = logging.getLogger(__name__)

ATTR_PROTOCOL = 'Protocol'
ATTR_REMOTE_HOST = 'Remote Server'
ATTR_REMOTE_PORT = 'Remote Port'
ATTR_VERSION = 'Version'

CONF_ATTRIBUTION = 'Data retrieved using Iperf3'
CONF_DURATION = 'duration'

DEFAULT_DURATION = 10
DEFAULT_PORT = 5201

SCAN_INTERVAL = timedelta(minutes=30)

ICON = 'mdi:speedometer'

SENSOR_TYPES = {
    'download': ['Download', 'Mbit/s'],
    'upload': ['Upload', 'Mbit/s'],
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_MONITORED_CONDITIONS):
        vol.All(cv.ensure_list, [vol.In(list(SENSOR_TYPES))]),
    vol.Required(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_DURATION, default=DEFAULT_DURATION): vol.Range(5, 10),
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Iperf3 sensor."""
    dev = []
    for sensor in config[CONF_MONITORED_CONDITIONS]:
        dev.append(
                Iperf3Sensor(config[CONF_HOST],
                             config[CONF_PORT],
                             config[CONF_DURATION],
                             sensor))
    add_devices(dev)

    def update(hass, call=None):
        """Update service for manual updates."""
        for sensor in dev:
            sensor.update()

    for sensor in dev:
        hass.services.register(DOMAIN, sensor.service_name, update)


class Iperf3Sensor(Entity):
    """A Iperf3 sensor implementation."""

    def __init__(self, server, port, duration, sensor_type):
        """Initialize the sensor."""
        self._attrs = {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
        }
        self._name = \
            "{} {}".format(SENSOR_TYPES[sensor_type][0], server)
        self._state = None
        self._sensor_type = sensor_type
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._port = port
        self._server = server
        self._duration = duration
        self.result = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def service_name(self):
        """Return the service name of the sensor."""
        return slugify("{} {}".format('update_iperf3', self._server))

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
        if self.result is not None:
            self._attrs[ATTR_ATTRIBUTION] = CONF_ATTRIBUTION
            self._attrs[ATTR_PROTOCOL] = self.result.protocol
            self._attrs[ATTR_REMOTE_HOST] = self.result.remote_host
            self._attrs[ATTR_REMOTE_PORT] = self.result.remote_port
            self._attrs[ATTR_VERSION] = self.result.version
        return self._attrs

    def update(self):
        """Get the latest data and update the states."""
        import iperf3
        client = iperf3.Client()
        client.duration = self._duration
        client.server_hostname = self._server
        client.port = self._port
        client.verbose = False

        # when testing download bandwith, reverse must be True
        if self._sensor_type == 'download':
            client.reverse = True

        try:
            self.result = client.run()
        except (OSError, AttributeError) as error:
            self.result = None
            _LOGGER.error("Iperf3 sensor error: %s", error)
            return

        if self.result is not None and \
           hasattr(self.result, 'error') and \
           self.result.error is not None:
            _LOGGER.error("Iperf3 sensor error: %s", self.result.error)
            self.result = None
            return

        if self._sensor_type == 'download':
            self._state = self.result.received_Mbps

        elif self._sensor_type == 'upload':
            self._state = self.result.sent_Mbps

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
