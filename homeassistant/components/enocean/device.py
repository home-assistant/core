"""Representation of an EnOcean device."""
from enocean.protocol.packet import Packet
from enocean.utils import combine_hex

from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send
from homeassistant.helpers.entity import Entity

from .const import SIGNAL_RECEIVE_MESSAGE, SIGNAL_SEND_MESSAGE


class EnOceanEntity(Entity):
    """Parent class for all entities associated with the EnOcean component."""

    def __init__(self, dev_id: list[int], dev_name: str) -> None:
        """Initialize the device."""
        self.dev_id = dev_id
        self.dev_name = dev_name

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_RECEIVE_MESSAGE, self._message_received_callback
            )
        )

    @property
    def full_device_name(self):
        """Return the device name including the device's EnOcean id."""
        return ((self.dev_name + " [" + self.dev_id_string() + "]").strip(),)

    def _message_received_callback(self, packet):
        """Handle incoming packets."""

        if packet.sender_int == combine_hex(self.dev_id):
            self.value_changed(packet)

    def value_changed(self, packet):
        """Update the internal state of the device when a packet arrives."""

    def send_command(self, data, optional, packet_type):
        """Send a command via the EnOcean dongle."""

        packet = Packet(packet_type, data=data, optional=optional)
        dispatcher_send(self.hass, SIGNAL_SEND_MESSAGE, packet)

    def dev_id_number(self):
        """Return the EnOcean id as integer."""
        return combine_hex(self.dev_id)

    def dev_id_string(self):
        """Return the EnOcean id as colon-separated hex string."""
        value = hex(self.dev_id_number())[2:].rjust(8, "0").upper()
        return ":".join(value[i : i + 2] for i in range(0, len(value), 2))
