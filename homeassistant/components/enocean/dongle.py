"""Representation of an EnOcean dongle."""

import glob
import logging
from os.path import basename, normpath
from urllib.parse import urlparse

from enocean.communicators import SerialCommunicator
from enocean.communicators.communicator import Communicator
from enocean.protocol.packet import RadioPacket
import serial

from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send

from .const import SIGNAL_RECEIVE_MESSAGE, SIGNAL_SEND_MESSAGE

_LOGGER = logging.getLogger(__name__)

# Supported pyserial URL schemes for network serial connections
SUPPORTED_URL_SCHEMES = ("rfc2217", "socket", "loop", "spy")


class EnOceanDongle:
    """Representation of an EnOcean dongle.

    The dongle is responsible for receiving the EnOcean frames,
    creating devices if needed, and dispatching messages to platforms.
    """

    def __init__(self, hass, serial_path):
        """Initialize the EnOcean dongle."""
        self.serial_path = serial_path
        self.hass = hass
        self.dispatcher_disconnect_handle = None
        self._communicator = None

        # For network URLs, use the netloc (host:port) as identifier
        # For local paths, use basename as before
        if _is_serial_url(serial_path):
            parsed = urlparse(serial_path)
            self.identifier = f"{parsed.scheme}_{parsed.netloc.replace(':', '_')}"
        else:
            self.identifier = basename(normpath(serial_path))

    def _create_serial_port(self, serial_path: str):
        """Create serial port (blocking operation, must run in executor)."""
        if _is_serial_url(serial_path):
            return serial.serial_for_url(serial_path, baudrate=57600, timeout=0.1)
        return None

    def _create_communicator(self, serial_path: str):
        """Create the SerialCommunicator (blocking operation, must run in executor)."""
        # For network URLs, we need to patch the serial port before passing to SerialCommunicator
        # because the enocean library uses serial.Serial() which doesn't support URL schemes
        if _is_serial_url(serial_path):
            # Pre-open the serial connection using serial_for_url to get a proper serial object
            serial_port = self._create_serial_port(serial_path)
            # Create a communicator by monkey-patching its serial object
            # Private member access is necessary to work around library limitation
            communicator = SerialCommunicator.__new__(SerialCommunicator)
            # Properly initialize the Communicator base class
            Communicator.__init__(communicator, callback=self.callback)
            # Inject the pre-opened serial port
            communicator._SerialCommunicator__ser = serial_port  # noqa: SLF001
            return communicator
        return SerialCommunicator(port=serial_path, callback=self.callback)

    async def async_setup(self):
        """Finish the setup of the bridge and supported platforms."""
        self._communicator.start()
        self.dispatcher_disconnect_handle = async_dispatcher_connect(
            self.hass, SIGNAL_SEND_MESSAGE, self._send_message_callback
        )

    def unload(self):
        """Disconnect callbacks established at init time."""
        if self.dispatcher_disconnect_handle:
            self.dispatcher_disconnect_handle()
            self.dispatcher_disconnect_handle = None

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


def _is_serial_url(path: str) -> bool:
    """Check if the path is a pyserial URL scheme."""
    return any(path.startswith(f"{scheme}://") for scheme in SUPPORTED_URL_SCHEMES)


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


def validate_path(path: str) -> bool:
    """Validate EnOcean dongle path.

    Supports both local device paths and network serial URLs.

    Supported formats:
    - Local: /dev/ttyUSB0, /dev/serial/by-id/...
    - RFC2217: rfc2217://hostname:port
    - Socket: socket://hostname:port
    - Other pyserial URLs: loop://, spy://

    Returns True if the path is valid, False otherwise.
    """
    # Support pyserial URL handlers for network serial devices
    if _is_serial_url(path):
        # Basic URL format validation
        parsed = urlparse(path)
        if not parsed.scheme:
            _LOGGER.warning("Invalid URL format: %s", path)
            return False
        # Some schemes like loop:// and spy:// don't require netloc
        # rfc2217:// and socket:// do require netloc
        if parsed.scheme in ("rfc2217", "socket") and not parsed.netloc:
            _LOGGER.warning("Invalid URL format: %s (missing host:port)", path)
            return False

        # Validate connection by attempting to create serial connection
        # Use serial_for_url for network URLs since SerialCommunicator uses serial.Serial()
        try:
            conn = serial.serial_for_url(path, baudrate=57600, timeout=0.1)
            conn.close()
        except serial.SerialException as exception:
            _LOGGER.warning("Cannot connect to %s: %s", path, str(exception))
            return False
        return True

    # Local device path validation (existing behavior)
    try:
        # Creating the serial communicator will raise an exception
        # if it cannot connect
        SerialCommunicator(port=path)
    except serial.SerialException as exception:
        _LOGGER.warning("Dongle path %s is invalid: %s", path, str(exception))
        return False
    return True
