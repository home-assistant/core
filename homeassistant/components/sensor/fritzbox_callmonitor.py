"""
A sensor to monitor incoming and outgoing phone calls on a Fritz!Box router.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.fritzbox_callmonitor/
"""
import logging
import socket
import threading
import datetime
import time

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_HOST, CONF_PORT, CONF_NAME)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)
DEFAULT_NAME = 'Phone'
DEFAULT_HOST = '169.254.1.1'  # IP valid for all Fritz!Box routers
DEFAULT_PORT = 1012

VALUE_DEFAULT = 'idle'
VALUE_RING = 'ringing'
VALUE_CALL = 'dialing'
VALUE_CONNECT = 'talking'
VALUE_DISCONNECT = 'idle'

INTERVAL_RECONNECT = 60

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup Fritz!Box call monitor sensor platform."""
    name = config.get(CONF_NAME)
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)

    sensor = FritzBoxCallSensor(name=name)

    add_devices([sensor])

    monitor = FritzBoxCallMonitor(host=host, port=port, sensor=sensor)
    monitor.connect()

    if monitor.sock is None:
        return False
    else:
        return True


# pylint: disable=too-few-public-methods
class FritzBoxCallSensor(Entity):
    """Implementation of a Fritz!Box call monitor."""

    def __init__(self, name):
        """Initialize the sensor."""
        self._state = VALUE_DEFAULT
        self._attributes = {}
        self._name = name

    def set_state(self, state):
        """Set the state."""
        self._state = state

    def set_attributes(self, attributes):
        """Set the state attributes."""
        self._attributes = attributes

    @property
    def should_poll(self):
        """No polling needed."""
        return False

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attributes


# pylint: disable=too-few-public-methods
class FritzBoxCallMonitor(object):
    """Event listener to monitor calls on the Fritz!Box."""

    def __init__(self, host, port, sensor):
        """Initialize Fritz!Box monitor instance."""
        self.host = host
        self.port = port
        self.sock = None
        self._sensor = sensor

    def connect(self):
        """Connect to the Fritz!Box."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(10)
        try:
            self.sock.connect((self.host, self.port))
            threading.Thread(target=self._listen, daemon=True).start()
        except socket.error as err:
            self.sock = None
            _LOGGER.error("Cannot connect to %s on port %s: %s",
                          self.host, self.port, err)

    def _listen(self):
        """Listen to incoming or outgoing calls."""
        while True:
            try:
                response = self.sock.recv(2048)
            except socket.timeout:
                # if no response after 10 seconds, just recv again
                continue
            response = str(response, "utf-8")

            if not response:
                # if the response is empty, the connection has been lost.
                # try to reconnect
                self.sock = None
                while self.sock is None:
                    self.connect()
                    time.sleep(INTERVAL_RECONNECT)
            else:
                line = response.split("\n", 1)[0]
                self._parse(line)
                time.sleep(1)
        return

    def _parse(self, line):
        """Parse the call information and set the sensor states."""
        line = line.split(";")
        df_in = "%d.%m.%y %H:%M:%S"
        df_out = "%Y-%m-%dT%H:%M:%S"
        isotime = datetime.datetime.strptime(line[0], df_in).strftime(df_out)
        if line[1] == "RING":
            self._sensor.set_state(VALUE_RING)
            att = {"type": "incoming",
                   "from": line[3],
                   "to": line[4],
                   "device": line[5],
                   "initiated": isotime}
            self._sensor.set_attributes(att)
        elif line[1] == "CALL":
            self._sensor.set_state(VALUE_CALL)
            att = {"type": "outgoing",
                   "from": line[4],
                   "to": line[5],
                   "device": line[6],
                   "initiated": isotime}
            self._sensor.set_attributes(att)
        elif line[1] == "CONNECT":
            self._sensor.set_state(VALUE_CONNECT)
            att = {"with": line[4], "device": [3], "accepted": isotime}
            self._sensor.set_attributes(att)
        elif line[1] == "DISCONNECT":
            self._sensor.set_state(VALUE_DISCONNECT)
            att = {"duration": line[3], "closed": isotime}
            self._sensor.set_attributes(att)
        self._sensor.update_ha_state()
