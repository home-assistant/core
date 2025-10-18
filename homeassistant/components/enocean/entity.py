"""Representation of an EnOcean device."""

from abc import abstractmethod

from enocean.protocol.packet import Packet

from homeassistant.config_entries import _LOGGER
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send
from homeassistant.helpers.entity import Entity

from .const import (
    DATA_ENOCEAN,
    DOMAIN,
    ENOCEAN_DONGLE,
    SIGNAL_RECEIVE_MESSAGE,
    SIGNAL_SEND_MESSAGE,
)
from .enocean_id import EnOceanID
from .supported_device_type import EnOceanSupportedDeviceType


class EnOceanEntity(Entity):
    """Parent class for all entities associated with the EnOcean component."""

    def __init__(
        self,
        enocean_device_id: EnOceanID,
        enocean_gateway_id: EnOceanID,
        device_name: str,
        name: str | None = None,
        dev_type: EnOceanSupportedDeviceType = EnOceanSupportedDeviceType(),
    ) -> None:
        """Initialize the entity."""
        super().__init__()
        self._enocean_device_id: EnOceanID = enocean_device_id
        self._device_name: str = device_name
        self.dev_type = dev_type
        self._attr_name = name
        self._attr_has_entity_name = name is not None
        self._gateway_id = enocean_gateway_id
        self._attr_should_poll = False
        # _LOGGER.warning("unique_id: %s", f"{enocean_device_id.to_string()}-{self.platform}-{name}")
        # self._attr_unique_id = f"{enocean_device_id.to_string()}-{self._attr_device_class}-{name}"

    async def async_added_to_hass(self) -> None:
        """Get gateway ID and register callback."""
        self._gateway_id = self.hass.data[DATA_ENOCEAN][ENOCEAN_DONGLE].chip_id

        _LOGGER.warning("Unique_id: %s", self.unique_id)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_RECEIVE_MESSAGE, self._message_received_callback
            )
        )

    def _message_received_callback(self, packet):
        """Handle incoming packets."""
        if packet.sender_int == self._enocean_device_id.to_number():
            self.value_changed(packet)

    @abstractmethod
    def value_changed(self, packet):
        """Update the internal state of the device when a packet arrives."""

    def send_command(self, data, optional, packet_type):
        """Send a command via the EnOcean dongle."""
        packet = Packet(packet_type, data=data, optional=optional)
        dispatcher_send(self.hass, SIGNAL_SEND_MESSAGE, packet)

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        uid = f"{self.enocean_device_id.to_string()}.{self.platform.domain}"
        if self.device_class:
            uid += f".{self.device_class}"
        else:
            uid += ".generic"

        if self.name:
            uid += f".{self.name}"
        return uid

    @property
    def enocean_device_id(self) -> EnOceanID:
        """Return the EnOcean id as EnOceanID."""
        return self._enocean_device_id

    @property
    def gateway_id(self) -> EnOceanID:
        """Return the gateway's chip id as colon-separated hex string (NOT YET IMPLEMENTED)."""
        return self._gateway_id

    @property
    def device_info(self):
        """Get device info."""

        info = {
            "name": self._device_name,
            "manufacturer": self.dev_type.manufacturer,
            "model": self.dev_type.model,
        }

        if self._enocean_device_id.to_number() == self._gateway_id.to_number():
            info.update(
                {
                    "identifiers": {(DOMAIN, self._enocean_device_id.to_string())},
                    "serial_number": self.hass.data[DATA_ENOCEAN][
                        ENOCEAN_DONGLE
                    ].chip_id.to_string(),
                    "sw_version": self.hass.data[DATA_ENOCEAN][
                        ENOCEAN_DONGLE
                    ].sw_version,
                    "hw_version": self.hass.data[DATA_ENOCEAN][
                        ENOCEAN_DONGLE
                    ].chip_version,
                }
            )
            return info

        info.update({"identifiers": {(DOMAIN, self._enocean_device_id.to_string())}})
        info.update({"serial_number": self._enocean_device_id.to_string()})
        info.update({"via_device": (DOMAIN, self.gateway_id.to_string())})
        info.update({"model_id": "EEP " + self.dev_type.eep})
        return info
