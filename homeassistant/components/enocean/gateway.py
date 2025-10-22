"""Representation of an EnOcean gateway."""

from collections.abc import Callable
import glob
import logging

from enocean.communicators import SerialCommunicator
from enocean.protocol.packet import Packet, RadioPacket
from enocean.utils import to_hex_string
from home_assistant_enocean.enocean_id import EnOceanID
import serial

from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send

from .const import SIGNAL_RECEIVE_MESSAGE, SIGNAL_SEND_MESSAGE

_LOGGER = logging.getLogger(__name__)


class EnOceanGateway:
    """Representation of an EnOcean gateway.

    The gateway is responsible for receiving the EnOcean frames,
    creating devices if needed, and dispatching messages to platforms.
    """

    def __init__(self, hass: HomeAssistant, serial_path: str) -> None:
        """Initialize the EnOcean gateway."""
        self.__communicator: SerialCommunicator = SerialCommunicator(port=serial_path)
        self.__hass: HomeAssistant = hass
        self.__dispatcher_disconnect_handle: Callable[[], None] | None = None
        self.__base_id: EnOceanID = EnOceanID(0)
        self.__chip_id: EnOceanID = EnOceanID(0)
        self.__chip_version: int = 0
        self.__sw_version: str = "n/a"

        # self.__binary_sensors: dict[str, object] = {}
        # self.__sensors: dict[str, object] = {}
        # self.__switches: dict[str, object] = {}
        # self.__covers: dict[str, object] = {}

    async def async_setup(self) -> None:
        """Finish the setup of the gateway and supported platforms."""
        self.__communicator.start()
        self.__chip_id = EnOceanID(to_hex_string(self.__communicator.chip_id))
        self.__base_id = EnOceanID(to_hex_string(self.__communicator.base_id))

        self.__chip_version = self.__communicator.version_info.chip_version
        # _LOGGER.warning("Version_info: %s", self.__communicator.version_info.__dict__)

        self.__sw_version = (
            self.__communicator.version_info.app_version.versionString()
            + " (App), "
            + self.__communicator.version_info.api_version.versionString()
            + " (API)"
        )

        # callback needs to be set after initialization
        # in order for chip_id and base_id to be available
        self.__communicator.callback = self.callback

        self.__dispatcher_disconnect_handle = async_dispatcher_connect(
            self.__hass, SIGNAL_SEND_MESSAGE, self._send_message_callback
        )

    def unload(self) -> None:
        """Disconnect callbacks established at init time."""
        if self.__dispatcher_disconnect_handle:
            self.__dispatcher_disconnect_handle()
            self.__dispatcher_disconnect_handle = None

        if self.__communicator:
            if self.__communicator.is_alive():
                self.__communicator.stop()

    @property
    def base_id(self) -> EnOceanID:
        """Get the gateway's base id."""
        return self.__base_id

    @property
    def chip_id(self) -> EnOceanID:
        """Get the gateway's chip id."""
        return self.__chip_id

    def valid_sender_ids(self) -> list[selector.SelectOptionDict]:
        """Return a list of valid sender ids."""

        if not self.__base_id or not self.__chip_id:
            return []

        valid_senders = [
            selector.SelectOptionDict(
                value=self.__chip_id.to_string(),
                label="Chip ID (" + self.__chip_id.to_string() + ")",
            ),
            selector.SelectOptionDict(
                value=self.__base_id.to_string(),
                label="Base ID (" + self.__base_id.to_string() + ")",
            ),
        ]
        base_id_int = self.__base_id.to_number()
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
        """Get the gateway's chip version."""
        return self.__chip_version

    @property
    def sw_version(self) -> str:
        """Get the gateway's software version."""
        return self.__sw_version

    def _send_message_callback(self, command: Packet) -> None:
        """Send a command through the EnOcean gateway."""
        self.__communicator.send(command)

    def callback(self, packet: Packet) -> None:
        """Handle EnOcean device's callback.

        This is the callback function called by python-enocean whenever there
        is an incoming packet.
        """
        if isinstance(packet, RadioPacket):
            _LOGGER.debug("Received radio packet: %s", packet)
            dispatcher_send(self.__hass, SIGNAL_RECEIVE_MESSAGE, packet)


def detect() -> list[str]:
    """Return a list of candidate paths for USB EnOcean gateways.

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
