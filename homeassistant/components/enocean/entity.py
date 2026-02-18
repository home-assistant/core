"""Representation of an EnOcean device."""

from enocean.protocol.packet import Packet
from enocean_async.erp1.address import EURID, Address, BaseAddress, SenderAddress
from enocean_async.erp1.telegram import ERP1Telegram

from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send
from homeassistant.helpers.entity import Entity

from .const import SIGNAL_RECEIVE_MESSAGE, SIGNAL_SEND_MESSAGE


class EnOceanEntity(Entity):
    """Parent class for all entities associated with the EnOcean component."""

    def __init__(self, dev_id: list[int]) -> None:
        """Initialize the device."""
        self.address: SenderAddress | None = None

        try:
            address = Address.from_bytelist(dev_id)
            if address.is_eurid():
                self.address = EURID.from_number(address.to_number())
            elif address.is_base_address():
                self.address = BaseAddress.from_number(address.to_number())
        except ValueError:
            self.address = None

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_RECEIVE_MESSAGE, self._message_received_callback
            )
        )

    def _message_received_callback(self, telegram: ERP1Telegram):
        """Handle incoming packets."""
        if not self.address:
            return

        if telegram.sender == self.address:
            self.value_changed(telegram)

    def value_changed(self, telegram: ERP1Telegram):
        """Update the internal state of the device when a packet arrives."""

    def send_command(self, data, optional, packet_type):
        """Send a command via the EnOcean dongle."""

        packet = Packet(packet_type, data=data, optional=optional)
        dispatcher_send(self.hass, SIGNAL_SEND_MESSAGE, packet)
