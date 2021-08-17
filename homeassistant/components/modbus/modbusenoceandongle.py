"""Representation of an EnOcean dongle based on a modbus hub."""

from homeassistant.components.enocean.const import SIGNAL_SEND_MESSAGE
from homeassistant.components.enocean.dongle import EnOceanDongle
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .modbusenoceanadapter import ModbusEnoceanAdapter
from .modbusenoceancommunicator import ModbusEnoceanCommunicator


class ModbusEnOceanDongle(EnOceanDongle):
    """Representation of an EnOcean dongle based on a modbus hub.

    The dongle is responsible for receiving the ENOcean frames,
    creating devices if needed, and dispatching messages to platforms.
    """

    def __init__(
        self, hass: HomeAssistant, adapter: ModbusEnoceanAdapter, esp_version: int
    ):
        """Initialize the EnOcean dongle."""

        self._communicator = ModbusEnoceanCommunicator(
            hass=hass, adapter=adapter, esp_version=esp_version, callback=self.callback
        )
        self.adapter = adapter
        self.identifier = adapter.identifier
        self.hass = hass
        self.dispatcher_disconnect_handle = None

    async def async_setup(self) -> None:
        """Finish the setup of the bridge and supported platforms."""
        self._communicator.start()
        self.dispatcher_disconnect_handle = async_dispatcher_connect(
            self.hass, SIGNAL_SEND_MESSAGE, self._send_message_callback
        )
