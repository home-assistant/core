"""Support for EnOcean events."""

from abc import abstractmethod
from collections.abc import Coroutine
from typing import Any

from enocean.protocol.packet import Packet

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.core import _LOGGER, HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .config_entry import EnOceanConfigEntry
from .const import (
    CONF_ENOCEAN_DEVICE_TYPE_ID,
    CONF_ENOCEAN_DEVICES,
    DOMAIN,
    ENOCEAN_BINARY_SENSOR_EEPS,
    SIGNAL_RECEIVE_MESSAGE,
)
from .enocean_device_type import EnOceanDeviceType
from .enocean_id import EnOceanID


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: EnOceanConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry."""

    devices = config_entry.options.get(CONF_ENOCEAN_DEVICES, [])

    for device in devices:
        device_type_id = device[CONF_ENOCEAN_DEVICE_TYPE_ID]
        device_type = EnOceanDeviceType.get_supported_device_types()[device_type_id]
        eep = device_type.eep

        if eep in ENOCEAN_BINARY_SENSOR_EEPS:
            device_id = EnOceanID(device["id"])

            async_add_entities(
                [
                    EnOceanButtonEvent(
                        enocean_id=device_id,
                        gateway_id=config_entry.runtime_data.gateway.chip_id,
                        device_name=device["name"],
                        device_type=device_type,
                        name=channel,
                    )
                    for channel in ("A0", "B0", "A1", "B1")
                ]
            )


class EnOceanEventEntity(EventEntity):
    """Representation of an EnOcean event entity."""

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
        self.__device_type = device_type
        self.__gateway_id = gateway_id

    async def async_added_to_hass(self) -> None:
        """Get gateway ID and register callback."""
        _LOGGER.warning(
            "Unique_id: %s, device_name: %s, entity_name: %s, Friendly_name: %s",
            self.unique_id,
            self.__device_name,
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
        """Value_changed method to be implemented by derived classes."""

    @property
    def unique_id(self) -> str:
        """Return a unique ID for this entity."""
        uid = f"{self.__enocean_id.to_string()}.{self.platform.domain}"

        if self.name:
            uid += f".{self.name}"
        return uid

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

        info.update({"via_device": (DOMAIN, self.__gateway_id.to_string())})
        info.update({"model_id": "EEP " + self.__device_type.eep})
        return info


class EnOceanButtonEvent(EnOceanEventEntity):
    """Button event entity for EnOcean devices."""

    _attr_device_class = EventDeviceClass.BUTTON
    _attr_event_types = [
        "single_click",
        "double_click",
        "long_press",
        "pushed",
        "released",
        "hold",
    ]

    def __init__(
        self,
        enocean_id: EnOceanID,
        gateway_id: EnOceanID,
        device_name: str,
        name: str,
        device_type: EnOceanDeviceType = EnOceanDeviceType(),
    ) -> None:
        """Initialize the EnOcean button event."""
        super().__init__(
            enocean_id=enocean_id,
            gateway_id=gateway_id,
            device_name=device_name,
            name=name,
            device_type=device_type,
        )

    @callback
    def _async_handle_event(self, event: str) -> None:
        """Handle the demo button event."""
        self._trigger_event(event, {"extra_data": 123})
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks with your device API/library."""
        await super().async_added_to_hass()
        # my_device_api.listen(self._async_handle_event)

    def async_will_remove_from_hass(self) -> Coroutine[Any, Any, None]:
        """Disconnect callbacks with your device API/library."""
        # my_device_api.unlisten(self._async_handle_event)
        return super().async_will_remove_from_hass()

    def value_changed(self, packet: Packet) -> None:
        """Fire an event with the data that have changed.

        This method is called when there is an incoming packet associated
        with this platform.

        Example packet data:
        - 2nd button pressed
            ['0xf6', '0x10', '0x00', '0x2d', '0xcf', '0x45', '0x30']
        - button released
            ['0xf6', '0x00', '0x00', '0x2d', '0xcf', '0x45', '0x20']
        """
        # Energy Bow
        # pushed = None

        # if packet.data[6] == 0x30:
        #     pushed = 1
        # elif packet.data[6] == 0x20:
        #     pushed = 0

        action = packet.data[1]

        # if action == 0x70:
        #     if self.name == "A0":
        #         self._attr_on = True
        # elif action == 0x50:
        #     if self.name == "A1":
        #         self._attr_on = True
        # elif action == 0x30:
        #     if self.name == "B0":
        #         self._attr_on = True
        # elif action == 0x10:
        #     if self.name == "B1":
        #         self._attr_on = True
        # elif action == 0x37:
        #     if self.name in ("A0", "B0", "AB0"):
        #         self._attr_on = True
        # elif action == 0x15:
        #     if self.name in ("A1", "B1", "AB1"):
        #         self._attr_on = True
        # elif action == 0x17:
        #     if self.name in ("A0", "B1"):
        #         self._attr_on = True
        # elif action == 0x35:
        #     if self.name in ("A1", "B0"):
        #         self._attr_on = True

        # elif action == 0x00:
        #     self._attr_on = False
        # else:
        #     _LOGGER.warning("Unknown action: %s", action)
        #     self._attr_on = False

        self._trigger_event("single_click", {"action": action})

        # self.async_write_ha_state()
        self.schedule_update_ha_state()
