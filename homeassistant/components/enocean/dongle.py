"""Representation of an EnOcean dongle."""
import glob
import logging
from os.path import basename, normpath

from enocean.communicators import SerialCommunicator
from enocean.protocol.packet import RadioPacket

from homeassistant.components.enocean.const import (
    LOGGER,
    SIGNAL_RECEIVE_MESSAGE,
    SIGNAL_SEND_MESSAGE,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect

_LOGGER = logging.getLogger(__name__)


class EnOceanDongle:
    """Representation of an EnOcean dongle."""

    """Representation of an EnOcean dongle.

    The dongle is responsible for receiving the ENOcean frames,
    creating devices if needed, and dispatching messages to platforms.
    """

    @classmethod
    def detect(cls):
        """Return a list of candidate paths for USB ENOcean dongles.

        This method is currently a bit simplistic, it may need to be
        improved to support more configurations and OS.
        """
        globs_to_test = ["/dev/tty*FTOA2PV*", "/dev/serial/by-id/*EnOcean*"]
        found_paths = []
        for current_glob in globs_to_test:
            found_paths.extend(glob.glob(current_glob))

        return found_paths

    def __init__(self, hass, serial_path):
        """Initialize the EnOcean dongle."""

        LOGGER.debug("Creating dongle for path %s", serial_path)
        self.__communicator = SerialCommunicator(
            port=serial_path, callback=self.callback
        )
        self.__communicator.start()
        self.serial_path = serial_path
        self.identifier = basename(normpath(serial_path))
        self.hass = hass
        async_dispatcher_connect(hass, SIGNAL_SEND_MESSAGE, self._send_message_callback)

    def _send_message_callback(self, command):
        """Send a command through the EnOcean dongle."""
        self.__communicator.send(command)

    def callback(self, packet):
        """Handle EnOcean device's callback.

        This is the callback function called by python-enocan whenever there
        is an incoming packet.
        """

        if isinstance(packet, RadioPacket):
            _LOGGER.debug("Received radio packet: %s", packet)
            self.hass.helpers.dispatcher.dispatcher_send(SIGNAL_RECEIVE_MESSAGE, packet)
