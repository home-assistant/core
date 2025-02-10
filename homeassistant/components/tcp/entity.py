"""Common code for TCP component."""

from __future__ import annotations

import logging
import select
import socket
import ssl
from typing import Final

from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PAYLOAD,
    CONF_PORT,
    CONF_SSL,
    CONF_TIMEOUT,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_VALUE_TEMPLATE,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType

from .const import CONF_BUFFER_SIZE, CONF_VALUE_ON
from .model import TcpSensorConfig

_LOGGER: Final = logging.getLogger(__name__)


class TcpEntity(Entity):
    """Base entity class for TCP platform."""

    def __init__(self, hass: HomeAssistant, config: ConfigType) -> None:
        """Set all the config values if they exist and get initial state."""

        self._hass = hass
        self._config: TcpSensorConfig = {
            CONF_NAME: config[CONF_NAME],
            CONF_HOST: config[CONF_HOST],
            CONF_PORT: config[CONF_PORT],
            CONF_TIMEOUT: config[CONF_TIMEOUT],
            CONF_PAYLOAD: config[CONF_PAYLOAD],
            CONF_UNIT_OF_MEASUREMENT: config.get(CONF_UNIT_OF_MEASUREMENT),
            CONF_VALUE_TEMPLATE: config.get(CONF_VALUE_TEMPLATE),
            CONF_VALUE_ON: config.get(CONF_VALUE_ON),
            CONF_BUFFER_SIZE: config[CONF_BUFFER_SIZE],
            CONF_SSL: config[CONF_SSL],
            CONF_VERIFY_SSL: config[CONF_VERIFY_SSL],
        }

        self._ssl_context: ssl.SSLContext | None = None
        if self._config[CONF_SSL]:
            self._ssl_context = ssl.create_default_context()
            if not self._config[CONF_VERIFY_SSL]:
                self._ssl_context.check_hostname = False
                self._ssl_context.verify_mode = ssl.CERT_NONE

        self._state: str | None = None
        self.update()

    @property
    def name(self) -> str:
        """Return the name of this sensor."""
        return self._config[CONF_NAME]

    def update(self) -> None:
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
                    (
                        "Timeout (%s second(s)) waiting for a response after "
                        "sending %r to %s on port %s"
                    ),
                    self._config[CONF_TIMEOUT],
                    self._config[CONF_PAYLOAD],
                    self._config[CONF_HOST],
                    self._config[CONF_PORT],
                )
                return

            value = sock.recv(self._config[CONF_BUFFER_SIZE]).decode()

        value_template = self._config[CONF_VALUE_TEMPLATE]
        if value_template is not None:
            try:
                self._state = value_template.render(parse_result=False, value=value)
            except TemplateError:
                _LOGGER.error(
                    "Unable to render template of %r with value: %r",
                    self._config[CONF_VALUE_TEMPLATE],
                    value,
                )
                return
            return

        self._state = value
