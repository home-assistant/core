"""Support for LIRC devices."""

import logging
import threading

import socket

from homeassistant.const import EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.exceptions import IntegrationError

_LOGGER = logging.getLogger(__name__)

BUTTON_NAME = "button_name"
BUTTON_CODE = "button_code"
DEVICE_NAME = "device_name"

DOMAIN = "lirc"

EVENT_IR_COMMAND_RECEIVED = "ir_command_received"

ICON = "mdi:remote"

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

SOCKET_PATH = "/var/run/lirc/lircd"

BUFFER_SIZE = 128


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    lirc_interface = LircInterface(hass)

    def _start_lirc(_event):
        lirc_interface.start()

    def _stop_lirc(_event):
        lirc_interface.stopped.set()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, _start_lirc)
    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, _stop_lirc)

    return True


class ConnectError(IntegrationError):
    """Error occurred when trying to connect to a socket."""


class LircInterface(threading.Thread):
    """Interfaces with the lirc daemon to read IR commands."""

    def __init__(self, hass):
        """Construct a LIRC interface object."""
        threading.Thread.__init__(self)
        self.daemon = True
        self.stopped = threading.Event()
        self.hass = hass

    def run(self):
        """Run the loop of the LIRC interface thread."""
        _LOGGER.debug("LIRC interface thread started")

        lirc_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

        try:
            lirc_socket.connect(SOCKET_PATH)
        except OSError as err:
            lirc_socket.close()
            raise ConnectError(
                "Can't connect to LIRC socket: %s" % SOCKET_PATH
            ) from err

        while not self.stopped.is_set():
            data = lirc_socket.recv(BUFFER_SIZE)
            _, code, name, device_name = data.split()
            _LOGGER.info("Got new LIRC event %s", name)
            self.hass.bus.fire(
                EVENT_IR_COMMAND_RECEIVED,
                {
                    BUTTON_NAME: name.decode("utf-8"),
                    BUTTON_CODE: code.decode("utf-8"),
                    DEVICE_NAME: device_name.decode("utf-8"),
                },
            )

        socket.close()
        _LOGGER.debug("LIRC interface thread stopped")
