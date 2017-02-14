"""
Support for sensors using LLAP protocol by Ciseco / Wireless Things.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.llap/
"""

import socket
import socketserver
import threading
import json
import logging

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_ID, CONF_NAME, CONF_PORT, CONF_PREFIX, CONF_SENSORS,
    CONF_UNIT_OF_MEASUREMENT)
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)


DEFAULT_NAME = "LLAP Sensor"
DEFAULT_PORT = 50140
DEFAULT_NETWORK = "Serial"


SENSORS_SCHEMA = vol.Schema({
    vol.Optional(CONF_NAME, default=None): cv.string,
    vol.Required(CONF_ID): vol.Match(r'^[A-Z\-#@?\\*]{2}$'),
    vol.Optional(CONF_PREFIX, default=None):
        vol.Match(r'^[A-Z0-9 !\\"#$%&\'()*+,\-.:;<=>?@[/\]^_`{|}~]{0,9}$'),
    vol.Optional(CONF_UNIT_OF_MEASUREMENT, default=None): cv.string,
})


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional('network', default=DEFAULT_NETWORK): cv.string,
    vol.Required(CONF_SENSORS): [SENSORS_SCHEMA],
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the LLAP Sensor."""
    port = config.get(CONF_PORT)
    network = config.get('network')

    sensors = config.get(CONF_SENSORS)
    devices = []

    for sensor in sensors:
        devices.append(
            LLAPSensor(
                sensor.get(CONF_NAME),
                port,
                network,
                sensor.get(CONF_ID),
                sensor.get(CONF_PREFIX),
                sensor.get(CONF_UNIT_OF_MEASUREMENT)
            )
        )

    add_devices(devices)


class UDPRequestHandler(socketserver.DatagramRequestHandler):
    """Handler for UDP datagrams."""

    def __init__(self, request, client_address, server, sensor):
        """Initialize UDP datagram handler."""
        self._sensor = sensor
        super(UDPRequestHandler, self).__init__(request,
                                                client_address,
                                                server)

    def handle(self):
        """Handle received UDP datagram.

        An example of received data (formatted for readability):
        {
          'type': 'WirelessMessage',
          'timestamp': '19 Jan 2017 22:27:52 +0000',
          'id': 'XX',
          'network': 'Raspberry Pi',
          'data': ['TEMP018.8']
        }
        """
        data = self.rfile.read()
        json_data = json.loads(data.decode('utf-8'))
        _LOGGER.debug('Received "%s"', json_data)
        if (json_data['id'] == self._sensor.sensor_id
                and json_data['network'] == self._sensor.network_id
                and json_data['data'][0].startswith(self._sensor.prefix)):
            self._sensor.value = float(
                json_data['data'][0][len(self._sensor.prefix):]
            )
            self._sensor.update_ha_state()


class UDPListener(socketserver.ThreadingUDPServer):
    """UDP Listener."""

    def server_bind(self):
        """Override of the server_bind method."""
        _LOGGER.debug("Binding...")
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        super(UDPListener, self).server_bind()

    def finish_request(self, request, client_address):
        """Override of the finish_request method."""
        UDPRequestHandler(request, client_address, self, self.sensor)


class LLAPSensor(Entity):
    """Representation of LLAP Sensor."""

    def __init__(self, name, port, network_id, sensor_id, prefix, unit):
        """Initialize the sensor."""
        if name:
            self._name = name
        else:
            self._name = "{} {}".format(DEFAULT_NAME, sensor_id)
        self.network_id = network_id
        self.sensor_id = sensor_id
        self.prefix = prefix
        self.unit = unit

        self.value = None

        listener = UDPListener(('', port), UDPRequestHandler)
        listener.sensor = self
        listener_thread = threading.Thread(target=listener.serve_forever)
        listener_thread.daemon = True
        listener_thread.start()

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.value

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self.unit
