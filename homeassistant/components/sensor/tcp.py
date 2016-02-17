"""
homeassistant.components.sensor.tcp
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Provides a sensor which gets its values from a TCP socket.
"""
import logging
import socket
import re
from select import select

from homeassistant.const import CONF_NAME, CONF_HOST
from homeassistant.helpers.entity import Entity
from homeassistant.components.tcp import (
    DOMAIN, CONF_PORT, CONF_TIMEOUT, CONF_PAYLOAD, CONF_UNIT, CONF_VALUE_REGEX,
    CONF_VALUE_ON, CONF_BUFFER_SIZE, DEFAULT_TIMEOUT, DEFAULT_BUFFER_SIZE
)


DEPENDENCIES = [DOMAIN]

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """ Create the Sensor. """
    if not Sensor.validate_config(config):
        return False
    add_entities((Sensor(config),))


class Sensor(Entity):
    """ Sensor Entity which gets its value from a TCP socket. """
    required = tuple()

    def __init__(self, config):
        """ Set all the config values if they exist and get initial state. """
        self._config = {
            CONF_NAME: config.get(CONF_NAME),
            CONF_HOST: config[CONF_HOST],
            CONF_PORT: config[CONF_PORT],
            CONF_TIMEOUT: config.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
            CONF_PAYLOAD: config[CONF_PAYLOAD],
            CONF_UNIT: config.get(CONF_UNIT),
            CONF_VALUE_REGEX: config.get(CONF_VALUE_REGEX),
            CONF_VALUE_ON: config.get(CONF_VALUE_ON),
            CONF_BUFFER_SIZE: config.get(
                CONF_BUFFER_SIZE, DEFAULT_BUFFER_SIZE),
        }
        self._state = None
        self.update()

    @classmethod
    def validate_config(cls, config):
        """ Ensure the config has all of the necessary values. """
        always_required = (CONF_HOST, CONF_PORT, CONF_PAYLOAD)
        for key in always_required + tuple(cls.required):
            if key not in config:
                _LOGGER.error(
                    "You must provide %r to create any TCP entity.", key)
                return False
        return True

    @property
    def name(self):
        name = self._config[CONF_NAME]
        if name is not None:
            return name
        return super(Sensor, self).name

    @property
    def state(self):
        return self._state

    @property
    def unit_of_measurement(self):
        return self._config[CONF_UNIT]

    def update(self):
        """ Get the latest value for this sensor. """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.connect((self._config[CONF_HOST], self._config[CONF_PORT]))
        except socket.error as err:
            _LOGGER.error(
                "Unable to connect to %s on port %s: %s",
                self._config[CONF_HOST], self._config[CONF_PORT], err)
            return
        try:
            sock.send(self._config[CONF_PAYLOAD].encode())
        except socket.error as err:
            _LOGGER.error(
                "Unable to send payload %r to %s on port %s: %s",
                self._config[CONF_PAYLOAD], self._config[CONF_HOST],
                self._config[CONF_PORT], err)
            return
        readable, _, _ = select([sock], [], [], self._config[CONF_TIMEOUT])
        if not readable:
            _LOGGER.warning(
                "Timeout (%s second(s)) waiting for a response after sending "
                "%r to %s on port %s.",
                self._config[CONF_TIMEOUT], self._config[CONF_PAYLOAD],
                self._config[CONF_HOST], self._config[CONF_PORT])
            return
        value = sock.recv(self._config[CONF_BUFFER_SIZE]).decode()
        if self._config[CONF_VALUE_REGEX] is not None:
            match = re.match(self._config[CONF_VALUE_REGEX], value)
            if match is None:
                _LOGGER.warning(
                    "Unable to match value using value_regex of %r: %r",
                    self._config[CONF_VALUE_REGEX], value)
                return
            try:
                self._state = match.groups()[0]
            except IndexError:
                _LOGGER.error(
                    "You must include a capture group in the regex for %r: %r",
                    self.name, self._config[CONF_VALUE_REGEX])
                return
            return
        self._state = value
