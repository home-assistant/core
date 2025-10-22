"""Representation of an EnOcean device."""

from abc import abstractmethod

from enocean.protocol.constants import PACKET
from enocean.protocol.packet import Packet

from homeassistant.config_entries import _LOGGER
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, SIGNAL_RECEIVE_MESSAGE, SIGNAL_SEND_MESSAGE
from .enocean_device_type import EnOceanDeviceType
from .enocean_id import EnOceanID


class EnOceanEntity(Entity):
    """Parent class for all entities associated with the EnOcean component."""

    def __init__(
        self,
        enocean_id: EnOceanID,
        gateway_id: EnOceanID,
        device_name: str,
        name: str | None = None,
        device_type: EnOceanDeviceType = EnOceanDeviceType(),
    ) -> None:
        """Initialize the entity."""
        super().__init__()

        # set base class attributes
        self._attr_name = name
        self._attr_has_entity_name = True
        self._attr_should_poll = False

        # define EnOcean-specific attributes
        self.__enocean_id: EnOceanID = enocean_id
        self.__device_name: str = device_name
        self.__device_type: EnOceanDeviceType = device_type
        self.__gateway_id: EnOceanID = gateway_id

    async def async_added_to_hass(self) -> None:
        """Get gateway ID and register callback."""
        _LOGGER.warning(
            "Unique_id: %s, entity_name: %s, Friendly_name: %s",
            self.unique_id,
            self.name,
            self._friendly_name_internal(),
        )

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_RECEIVE_MESSAGE, self._message_received_callback
            )
        )

    def _message_received_callback(self, packet: Packet) -> None:
        """Handle incoming packets."""
        if packet.sender_int == self.__enocean_id.to_number():
            self.value_changed(packet)

    @abstractmethod
    def value_changed(self, packet: Packet) -> None:
        """Update the internal state of the device when a packet arrives."""

    def send_command(
        self, data: None | list, optional: None | list, packet_type: PACKET
    ) -> None:
        """Send a command via the EnOcean dongle."""
        packet = Packet(packet_type, data=data, optional=optional)
        dispatcher_send(self.hass, SIGNAL_SEND_MESSAGE, packet)

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        uid = f"{self.enocean_id.to_string()}.{self.platform.domain}"

        if self.name:
            uid += f".{self.name}"
        return uid

    @property
    def enocean_id(self) -> EnOceanID:
        """Return the EnOcean device id."""
        return self.__enocean_id

    @property
    def gateway_id(self) -> EnOceanID:
        """Return the gateway's chip id."""
        return self.__gateway_id

    @property
    def device_info(self) -> DeviceInfo | None:
        """Get device info."""

        info = DeviceInfo(
            {
                "identifiers": {(DOMAIN, self.__enocean_id.to_string())},
                "name": self.__device_name,
                "manufacturer": self.__device_type.manufacturer,
                "model": self.__device_type.model,
                "serial_number": self.__enocean_id.to_string(),
                "sw_version": None,
                "hw_version": None,
                "model_id": None,
            }
        )

        if self.__enocean_id.to_number() == self.__gateway_id.to_number():
            if self.platform.config_entry is None:
                return info
            info.update(
                {
                    "sw_version": self.platform.config_entry.runtime_data.gateway.sw_version,
                    "hw_version": self.platform.config_entry.runtime_data.gateway.chip_version,
                }
            )
            return info

        info.update({"via_device": (DOMAIN, self.gateway_id.to_string())})
        info.update({"model_id": "EEP " + self.__device_type.eep})
        return info
