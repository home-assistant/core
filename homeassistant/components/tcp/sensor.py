"""Support for TCP socket based sensors."""
import logging
import select
import socket
import ssl

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PAYLOAD,
    CONF_PORT,
    CONF_TIMEOUT,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.exceptions import TemplateError
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

CONF_BUFFER_SIZE = "buffer_size"
CONF_VALUE_ON = "value_on"

DEFAULT_BUFFER_SIZE = 1024
DEFAULT_NAME = "TCP Sensor"
DEFAULT_TIMEOUT = 10
DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = True

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PORT): cv.port,
        vol.Required(CONF_PAYLOAD): cv.string,
        vol.Optional(CONF_BUFFER_SIZE, default=DEFAULT_BUFFER_SIZE): cv.positive_int,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
        vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
        vol.Optional(CONF_VALUE_ON): cv.string,
        vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
        vol.Optional(CONF_SSL, default=DEFAULT_SSL): cv.boolean,
        vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): cv.boolean,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the TCP Sensor."""
    add_entities([TcpSensor(hass, config)])


class TcpSensor(Entity):
    """Implementation of a TCP socket based sensor."""

    required = ()

    def __init__(self, hass, config):
        """Set all the config values if they exist and get initial state."""
        value_template = config.get(CONF_VALUE_TEMPLATE)

        if value_template is not None:
            value_template.hass = hass

        self._hass = hass
        self._config = {
            CONF_NAME: config.get(CONF_NAME),
            CONF_HOST: config.get(CONF_HOST),
            CONF_PORT: config.get(CONF_PORT),
            CONF_TIMEOUT: config.get(CONF_TIMEOUT),
            CONF_PAYLOAD: config.get(CONF_PAYLOAD),
            CONF_UNIT_OF_MEASUREMENT: config.get(CONF_UNIT_OF_MEASUREMENT),
            CONF_VALUE_TEMPLATE: value_template,
            CONF_VALUE_ON: config.get(CONF_VALUE_ON),
            CONF_BUFFER_SIZE: config.get(CONF_BUFFER_SIZE),
        }

        if config.get(CONF_SSL):
            self._ssl_context = ssl.create_default_context()
            if not config.get(CONF_VERIFY_SSL):
                self._ssl_context.check_hostname = False
                self._ssl_context.verify_mode = ssl.CERT_NONE
        else:
            self._ssl_context = None

        self._state = None
        self.update()

    @property
    def name(self):
        """Return the name of this sensor."""
        return self._config[CONF_NAME]

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return self._config[CONF_UNIT_OF_MEASUREMENT]

    def update(self):
        """Get the latest value for this sensor."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(self._config[CONF_TIMEOUT])
            try:
                sock.connect((self._config[CONF_HOST], self._config[CONF_PORT]))
            except OSError as err:
                _LOGGER.error(
                    "Unable to connect to %s on port %s: %s",
                    self._config[CONF_HOST],
                    self._config[CONF_PORT],
                    err,
                )
                return

            if self._ssl_context is not None:
                sock = self._ssl_context.wrap_socket(
                    sock, server_hostname=self._config[CONF_HOST]
                )

            try:
                sock.send(self._config[CONF_PAYLOAD].encode())
            except OSError as err:
                _LOGGER.error(
                    "Unable to send payload %r to %s on port %s: %s",
                    self._config[CONF_PAYLOAD],
                    self._config[CONF_HOST],
                    self._config[CONF_PORT],
                    err,
                )
                return

            readable, _, _ = select.select([sock], [], [], self._config[CONF_TIMEOUT])
            if not readable:
                _LOGGER.warning(
                    "Timeout (%s second(s)) waiting for a response after "
                    "sending %r to %s on port %s",
                    self._config[CONF_TIMEOUT],
                    self._config[CONF_PAYLOAD],
                    self._config[CONF_HOST],
                    self._config[CONF_PORT],
                )
                return

            value = sock.recv(self._config[CONF_BUFFER_SIZE]).decode()

        if self._config[CONF_VALUE_TEMPLATE] is not None:
            try:
                self._state = self._config[CONF_VALUE_TEMPLATE].render(
                    parse_result=False, value=value
                )
                return
            except TemplateError:
                _LOGGER.error(
                    "Unable to render template of %r with value: %r",
                    self._config[CONF_VALUE_TEMPLATE],
                    value,
                )
                return

        self._state = value
