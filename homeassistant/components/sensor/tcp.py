"""
Support for TCP socket based sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.tcp/
"""
import logging
import socket
import select

from homeassistant.const import CONF_NAME, CONF_HOST
from homeassistant.helpers import template
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.entity import Entity

CONF_PORT = "port"
CONF_TIMEOUT = "timeout"
CONF_PAYLOAD = "payload"
CONF_UNIT = "unit"
CONF_VALUE_TEMPLATE = "value_template"
CONF_VALUE_ON = "value_on"
CONF_BUFFER_SIZE = "buffer_size"

DEFAULT_TIMEOUT = 10
DEFAULT_BUFFER_SIZE = 1024

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Setup the TCP Sensor."""
    if not Sensor.validate_config(config):
        return False
    add_entities((Sensor(hass, config),))


class Sensor(Entity):
    """Implementation of a TCP socket based sensor."""

    required = tuple()

    def __init__(self, hass, config):
        """Set all the config values if they exist and get initial state."""
        self._hass = hass
        self._config = {
            CONF_NAME: config.get(CONF_NAME),
            CONF_HOST: config[CONF_HOST],
            CONF_PORT: config[CONF_PORT],
            CONF_TIMEOUT: config.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
            CONF_PAYLOAD: config[CONF_PAYLOAD],
            CONF_UNIT: config.get(CONF_UNIT),
            CONF_VALUE_TEMPLATE: config.get(CONF_VALUE_TEMPLATE),
            CONF_VALUE_ON: config.get(CONF_VALUE_ON),
            CONF_BUFFER_SIZE: config.get(
                CONF_BUFFER_SIZE, DEFAULT_BUFFER_SIZE),
        }
        self._state = None
        self.update()

    @classmethod
    def validate_config(cls, config):
        """Ensure the configuration has all of the necessary values."""
        always_required = (CONF_HOST, CONF_PORT, CONF_PAYLOAD)
        for key in always_required + tuple(cls.required):
            if key not in config:
                _LOGGER.error(
                    "You must provide %r to create any TCP entity.", key)
                return False
        return True

    @property
    def name(self):
        """Return the name of this sensor."""
        name = self._config[CONF_NAME]
        if name is not None:
            return name
        return super(Sensor, self).name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return self._config[CONF_UNIT]

    def update(self):
        """Get the latest value for this sensor."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(self._config[CONF_TIMEOUT])
            try:
                sock.connect(
                    (self._config[CONF_HOST], self._config[CONF_PORT]))
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

            readable, _, _ = select.select(
                [sock], [], [], self._config[CONF_TIMEOUT])
            if not readable:
                _LOGGER.warning(
                    "Timeout (%s second(s)) waiting for a response after "
                    "sending %r to %s on port %s.",
                    self._config[CONF_TIMEOUT], self._config[CONF_PAYLOAD],
                    self._config[CONF_HOST], self._config[CONF_PORT])
                return

            value = sock.recv(self._config[CONF_BUFFER_SIZE]).decode()

        if self._config[CONF_VALUE_TEMPLATE] is not None:
            try:
                self._state = template.render(
                    self._hass,
                    self._config[CONF_VALUE_TEMPLATE],
                    value=value)
                return
            except TemplateError as err:
                _LOGGER.error(
                    "Unable to render template of %r with value: %r",
                    self._config[CONF_VALUE_TEMPLATE], value)
                return

        self._state = value
