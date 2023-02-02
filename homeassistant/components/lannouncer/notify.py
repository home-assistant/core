"""Lannouncer platform for notify component."""
from __future__ import annotations

import logging
import socket
from urllib.parse import urlencode

import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

ATTR_METHOD = "method"
ATTR_METHOD_DEFAULT = "speak"
ATTR_METHOD_ALLOWED = ["speak", "alarm"]

DEFAULT_PORT = 1035

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)

_LOGGER = logging.getLogger(__name__)


def get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> LannouncerNotificationService:
    """Get the Lannouncer notification service."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)

    return LannouncerNotificationService(hass, host, port)


class LannouncerNotificationService(BaseNotificationService):
    """Implementation of a notification service for Lannouncer."""

    def __init__(self, hass, host, port):
        """Initialize the service."""
        self._hass = hass
        self._host = host
        self._port = port

    def send_message(self, message="", **kwargs):
        """Send a message to Lannouncer."""
        data = kwargs.get(ATTR_DATA)
        if data is not None and ATTR_METHOD in data:
            method = data.get(ATTR_METHOD)
        else:
            method = ATTR_METHOD_DEFAULT

        if method not in ATTR_METHOD_ALLOWED:
            _LOGGER.error("Unknown method %s", method)
            return

        cmd = urlencode({method: message})

        try:
            # Open socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((self._host, self._port))

            # Send message
            _LOGGER.debug("Sending message: %s", cmd)
            sock.sendall(cmd.encode())
            sock.sendall(b"&@DONE@\n")

            # Check response
            buffer = sock.recv(1024)
            if buffer != b"LANnouncer: OK":
                _LOGGER.error("Error sending data to Lannnouncer: %s", buffer.decode())

            # Close socket
            sock.close()
        except socket.gaierror:
            _LOGGER.error("Unable to connect to host %s", self._host)
        except OSError:
            _LOGGER.exception("Failed to send data to Lannnouncer")
