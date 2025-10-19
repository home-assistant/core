"""Representation of an EnOcean dongle."""

from collections.abc import Callable
import glob
import logging
from os.path import basename, normpath

from enocean.communicators import SerialCommunicator
from enocean.protocol.packet import Packet, RadioPacket
from enocean.utils import to_hex_string
import serial

from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send

from .const import SIGNAL_RECEIVE_MESSAGE, SIGNAL_SEND_MESSAGE
from .enocean_id import EnOceanID

_LOGGER = logging.getLogger(__name__)


class EnOceanDongle:
    """Representation of an EnOcean dongle.

    The dongle is responsible for receiving the EnOcean frames,
    creating devices if needed, and dispatching messages to platforms.
    """

    def __init__(self, hass: HomeAssistant, serial_path: str) -> None:
        """Initialize the EnOcean dongle."""

        # callback needs to be set after initialization
        # in order for chip_id and base_id to be available
        self._communicator = SerialCommunicator(port=serial_path)
        self.serial_path = serial_path
        self.identifier = basename(normpath(serial_path))
        self.hass = hass
        self.dispatcher_disconnect_handle: Callable[[], None] | None = None
        self._base_id: EnOceanID = EnOceanID(0)
        self._chip_id: EnOceanID = EnOceanID(0)
        self._chip_version: int = 0
        self._sw_version: str = "n/a"

    async def async_setup(self) -> None:
        """Finish the setup of the bridge and supported platforms."""
        self._communicator.start()
        self._chip_id = EnOceanID(to_hex_string(self._communicator.chip_id))
        self._base_id = EnOceanID(to_hex_string(self._communicator.base_id))

        self._chip_version = self._communicator.version_info.chip_version

        self._sw_version = (
            self._communicator.version_info.app_version.versionString()
            + " (App), "
            + self._communicator.version_info.api_version.versionString()
            + " (API)"
        )

        # callback needs to be set after initialization
        # in order for chip_id and base_id to be available
        self._communicator.callback = self.callback

        self.dispatcher_disconnect_handle = async_dispatcher_connect(
            self.hass, SIGNAL_SEND_MESSAGE, self._send_message_callback
        )

    def unload(self) -> None:
        """Disconnect callbacks established at init time."""
        if self.dispatcher_disconnect_handle:
            self.dispatcher_disconnect_handle()
            self.dispatcher_disconnect_handle = None

        if self._communicator:
            if self._communicator.is_alive():
                self._communicator.stop()

    @property
    def base_id(self) -> EnOceanID:
        """Get the dongle's base id."""
        return self._base_id

    @property
    def chip_id(self) -> EnOceanID:
        """Get the dongle's chip id."""
        return self._chip_id

    def valid_sender_ids(self) -> list[selector.SelectOptionDict]:
        """Return a list of valid sender ids."""

        if not self._base_id or not self._chip_id:
            return []

        valid_senders = [
            selector.SelectOptionDict(
                value=self._chip_id.to_string(),
                label="Chip ID (" + self._chip_id.to_string() + ")",
            ),
            selector.SelectOptionDict(
                value=self._base_id.to_string(),
                label="Base ID (" + self._base_id.to_string() + ")",
            ),
        ]
        base_id_int = self._base_id.to_number()
        valid_senders.extend(
            [
                selector.SelectOptionDict(
                    value=EnOceanID(base_id_int + i).to_string(),
                    label="Base ID + "
                    + str(i)
                    + " ("
                    + EnOceanID(base_id_int + i).to_string()
                    + ")",
                )
                for i in range(1, 128)
            ]
        )

        return valid_senders

    @property
    def chip_version(self) -> int:
        """Get the dongle's chip version."""
        return self._chip_version

    @property
    def sw_version(self) -> str:
        """Get the dongle's software version."""
        return self._sw_version

    def _send_message_callback(self, command: Packet) -> None:
        """Send a command through the EnOcean dongle."""
        self._communicator.send(command)

    def callback(self, packet: Packet) -> None:
        """Handle EnOcean device's callback.

        This is the callback function called by python-enocean whenever there
        is an incoming packet.
        """
        if isinstance(packet, RadioPacket):
            _LOGGER.debug("Received radio packet: %s", packet)
            dispatcher_send(self.hass, SIGNAL_RECEIVE_MESSAGE, packet)


def detect() -> list[str]:
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
    """Return True if the provided path points to a valid serial port, False otherwise."""
    try:
        # Creating the serial communicator will raise an exception
        # if it cannot connect
        SerialCommunicator(port=path)
    except serial.SerialException as exception:
        _LOGGER.warning("Dongle path %s is invalid: %s", path, str(exception))
        return False
    return True
