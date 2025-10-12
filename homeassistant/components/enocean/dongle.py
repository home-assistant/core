"""Representation of an EnOcean dongle."""

import glob
import logging
from os.path import basename, normpath

from enocean.communicators import SerialCommunicator
from enocean.protocol.packet import RadioPacket
from enocean.utils import to_hex_string
import serial

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send

from .const import SIGNAL_RECEIVE_MESSAGE, SIGNAL_SEND_MESSAGE

_LOGGER = logging.getLogger(__name__)


class EnOceanDongle:
    """Representation of an EnOcean dongle.

    The dongle is responsible for receiving the EnOcean frames,
    creating devices if needed, and dispatching messages to platforms.
    """

    def __init__(self, hass: HomeAssistant, serial_path) -> None:
        """Initialize the EnOcean dongle."""

        # callback needs to be set after initialization
        # in order for chip_id and base_id to be available
        self._communicator = SerialCommunicator(
            port=serial_path  # , callback=self.callback
        )
        self.serial_path = serial_path
        self.identifier = basename(normpath(serial_path))
        self.hass = hass
        self.dispatcher_disconnect_handle = None
        self._base_id = "00:00:00:00"
        self._chip_id = "00:00:00:00"
        self._chip_version = "n/a"
        self._sw_version = "n/a"

    async def async_setup(self):
        """Finish the setup of the bridge and supported platforms."""
        self._communicator.start()
        self._chip_id = to_hex_string(self._communicator.chip_id)
        self._base_id = to_hex_string(self._communicator.base_id)
        self._chip_version = self._communicator.version_info.chip_version

        self._sw_version = (
            self._communicator.version_info.app_version.versionString()
            + " (app), "
            + self._communicator.version_info.api_version.versionString()
            + " (api)"
        )

        # callback needs to be set after initialization
        # in order for chip_id and base_id to be available
        self._communicator.callback = self.callback

        #  _LOGGER.warning("Chip id: %s", self.chip_id)
        #  _LOGGER.warning("Base id: %s", self.base_id)
        self.dispatcher_disconnect_handle = async_dispatcher_connect(
            self.hass, SIGNAL_SEND_MESSAGE, self._send_message_callback
        )

    def unload(self):
        """Disconnect callbacks established at init time."""
        if self.dispatcher_disconnect_handle:
            self.dispatcher_disconnect_handle()
            self.dispatcher_disconnect_handle = None

    @property
    def base_id(self):
        """Get the dongle's base id."""
        return self._base_id

    @property
    def chip_id(self):
        """Get the dongle's chip id (REQUIRES UPDATE OF ENOCEAN LIBRARY)."""
        return self._chip_id

    def valid_sender_ids(self):
        """Return a list of valid sender ids (currently only the base id)."""
        valid_senders = [self._chip_id]
        # base_id_int = int(self._base_id.replace(":", ""), 16)
        # for i in range(1, 255):
        #     id_string
        #     valid_senders.append(to_hex_string(base_id_int + i))
        valid_senders.append(self._base_id)

    @property
    def chip_version(self):
        """Get the dongle's chip version."""
        return self._chip_version

    @property
    def sw_version(self):
        """Get the dongle's base id."""
        return self._sw_version

    def _send_message_callback(self, command):
        """Send a command through the EnOcean dongle."""
        self._communicator.send(command)

    def callback(self, packet):
        """Handle EnOcean device's callback.

        This is the callback function called by python-enocean whenever there
        is an incoming packet.
        """
        if isinstance(packet, RadioPacket):
            _LOGGER.debug("Received radio packet: %s", packet)
            dispatcher_send(self.hass, SIGNAL_RECEIVE_MESSAGE, packet)


def detect():
    """Return a list of candidate paths for USB EnOcean dongles.

    This method is currently a bit simplistic, it may need to be
    improved to support more configurations and OS.
    """
    globs_to_test = ["/dev/tty*FTOA2PV*", "/dev/serial/by-id/*EnOcean*"]
    found_paths = []
    for current_glob in globs_to_test:
        found_paths.extend(glob.glob(current_glob))

    return found_paths


def validate_path(path: str):
    """Return True if the provided path points to a valid serial port, False otherwise."""
    try:
        # Creating the serial communicator will raise an exception
        # if it cannot connect
        SerialCommunicator(port=path)
    except serial.SerialException as exception:
        _LOGGER.warning("Dongle path %s is invalid: %s", path, str(exception))
        return False
    return True
