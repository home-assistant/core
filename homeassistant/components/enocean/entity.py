"""Representation of an EnOcean device."""

from enocean_async import EURID, BaseAddress, SenderAddress
from enocean_async.address import Address
from enocean_async.protocol.erp1.telegram import ERP1Telegram
from enocean_async.protocol.esp3.packet import ESP3Packet, ESP3PacketType

from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send
from homeassistant.helpers.entity import Entity

from .const import LOGGER, SIGNAL_RECEIVE_MESSAGE, SIGNAL_SEND_MESSAGE


def combine_hex(dev_id: list[int]) -> int:
    """Combine list of integer values to one big integer.

    This function replaces the previously used function from the enocean library and is considered tech debt that will have to be replaced.
    """
    value = 0
    for byte in dev_id:
        value = (value << 8) | (byte & 0xFF)
    return value


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

    def _message_received_callback(self, telegram: ERP1Telegram) -> None:
        """Handle incoming packets."""
        if not self.address:
            return

        if telegram.sender == self.address:
            self.value_changed(telegram)

    def value_changed(self, telegram: ERP1Telegram) -> None:
        """Update the internal state of the device when a packet arrives."""

    def send_command(
        self, data: list[int], optional: list[int], packet_type: ESP3PacketType
    ) -> None:
        """Send a command via the EnOcean dongle, if data and optional are valid bytes; otherwise, ignore."""
        try:
            packet = ESP3Packet(packet_type, data=bytes(data), optional=bytes(optional))
            dispatcher_send(self.hass, SIGNAL_SEND_MESSAGE, packet)
        except ValueError as err:
            LOGGER.warning(
                "Failed to send command: invalid data or optional bytes: %s", err
            )


class NewEnOceanEntity(Entity):
    """New representation of an EnOcean device."""

    _attr_has_entity_name = True

    def __init__(
        self, eurid: EURID, enocean_entity_id: str, sender: SenderAddress | None = None
    ) -> None:
        """Initialize the device."""
        super().__init__()
        self.eurid = eurid
        self.enocean_entity_id = enocean_entity_id
        self._attr_unique_id = f"{eurid.to_string()}.{enocean_entity_id}"

        # legacy naming; to be removed once all entities have been migrated to the new format
        self._attr_name = f"EnOcean {eurid.to_string()} {enocean_entity_id}"
