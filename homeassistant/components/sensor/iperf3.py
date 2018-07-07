"""
Support for Iperf3 network measurement tool.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.iperf3/
"""
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.sensor import DOMAIN, PLATFORM_SCHEMA
from homeassistant.const import (
    ATTR_ATTRIBUTION, ATTR_ENTITY_ID, CONF_MONITORED_CONDITIONS,
    CONF_HOST, CONF_PORT, CONF_PROTOCOL)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['iperf3==0.1.10']

_LOGGER = logging.getLogger(__name__)

ATTR_PROTOCOL = 'Protocol'
ATTR_REMOTE_HOST = 'Remote Server'
ATTR_REMOTE_PORT = 'Remote Port'
ATTR_VERSION = 'Version'

CONF_ATTRIBUTION = 'Data retrieved using Iperf3'
CONF_DURATION = 'duration'
CONF_PARALLEL = 'parallel'

DEFAULT_DURATION = 10
DEFAULT_PORT = 5201
DEFAULT_PARALLEL = 1
DEFAULT_PROTOCOL = 'tcp'

IPERF3_DATA = 'iperf3'

SCAN_INTERVAL = timedelta(minutes=60)

SERVICE_NAME = 'iperf3_update'

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
    vol.Optional(CONF_PARALLEL, default=DEFAULT_PARALLEL): vol.Range(1, 20),
    vol.Optional(CONF_PROTOCOL, default=DEFAULT_PROTOCOL):
        vol.In(['tcp', 'udp']),
})


SERVICE_SCHEMA = vol.Schema({
    vol.Optional(ATTR_ENTITY_ID): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Iperf3 sensor."""
    if hass.data.get(IPERF3_DATA) is None:
        hass.data[IPERF3_DATA] = {}
        hass.data[IPERF3_DATA]['sensors'] = []

    dev = []
    for sensor in config[CONF_MONITORED_CONDITIONS]:
        dev.append(
            Iperf3Sensor(config[CONF_HOST],
                         config[CONF_PORT],
                         config[CONF_DURATION],
                         config[CONF_PARALLEL],
                         config[CONF_PROTOCOL],
                         sensor))

    hass.data[IPERF3_DATA]['sensors'].extend(dev)
    add_devices(dev)

    def _service_handler(service):
        """Update service for manual updates."""
        entity_id = service.data.get('entity_id')
        all_iperf3_sensors = hass.data[IPERF3_DATA]['sensors']

        for sensor in all_iperf3_sensors:
            if entity_id is not None:
                if sensor.entity_id == entity_id:
                    sensor.update()
                    sensor.schedule_update_ha_state()
                    break
            else:
                sensor.update()
                sensor.schedule_update_ha_state()

    for sensor in dev:
        hass.services.register(DOMAIN, SERVICE_NAME, _service_handler,
                               schema=SERVICE_SCHEMA)


class Iperf3Sensor(Entity):
    """A Iperf3 sensor implementation."""

    def __init__(self, server, port, duration, streams,
                 protocol, sensor_type):
        """Initialize the sensor."""
        self._attrs = {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
            ATTR_PROTOCOL: protocol,
        }
        self._name = \
            "{} {}".format(SENSOR_TYPES[sensor_type][0], server)
        self._state = None
        self._sensor_type = sensor_type
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]
        self._port = port
        self._server = server
        self._duration = duration
        self._num_streams = streams
        self._protocol = protocol
        self.result = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

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
        client.num_streams = self._num_streams
        client.protocol = self._protocol

        # when testing download bandwith, reverse must be True
        if self._sensor_type == 'download':
            client.reverse = True

        try:
            self.result = client.run()
        except (AttributeError, OSError, ValueError) as error:
            self.result = None
            _LOGGER.error("Iperf3 sensor error: %s", error)
            return

        if self.result is not None and \
           hasattr(self.result, 'error') and \
           self.result.error is not None:
            _LOGGER.error("Iperf3 sensor error: %s", self.result.error)
            self.result = None
            return

        # UDP only have 1 way attribute
        if self._protocol == 'udp':
            self._state = round(self.result.Mbps, 2)

        elif self._sensor_type == 'download':
            self._state = round(self.result.received_Mbps, 2)

        elif self._sensor_type == 'upload':
            self._state = round(self.result.sent_Mbps, 2)

    @property
    def icon(self):
        """Return icon."""
        return ICON
