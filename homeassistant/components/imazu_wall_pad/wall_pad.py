"""Wall Pad device class."""
from datetime import timedelta
import logging
from typing import Generic, TypeVar

from wp_imazu.packet import ImazuPacket

from homeassistant.const import Platform
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoredExtraData, RestoreEntity
from homeassistant.util import Throttle

from . import ImazuGateway
from .const import (
    ATTR_DEVICE,
    ATTR_ROOM_ID,
    ATTR_SUB_ID,
    BRAND_NAME,
    DOMAIN,
    MANUFACTURER,
    MODEL,
    PACKET,
    SW_VERSION,
)
from .helper import host_to_last

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T", bound=ImazuPacket)

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=90)


class WallPadDevice(Generic[T], RestoreEntity):
    """Defines a Wall Pad Device entity."""

    _attr_should_poll = True

    def __init__(self, gateway: ImazuGateway, platform: Platform, packet: T) -> None:
        """Initialize the instance."""
        self.gateway = gateway
        self.packet = packet
        self.entity_id = (
            f"{str(platform.value)}."
            f"{BRAND_NAME}_{host_to_last(self.gateway.host)}_"
            f"{self.packet.name.lower()}_{packet.room_id}_{packet.sub_id}"
        )
        self._attr_unique_id = (
            f"{BRAND_NAME}_{host_to_last(self.gateway.host)}_{self.packet.device_id}"
        )
        self._attr_name = (
            f"{BRAND_NAME} {packet.name} {packet.room_id}-{packet.sub_id}".title()
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{str(packet.device.value)}_{packet.room_id}")},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=f"{BRAND_NAME} {packet.name} {packet.room_id}".title(),
            sw_version=SW_VERSION,
            via_device=(DOMAIN, self.gateway.host),
        )
        self._attr_extra_state_attributes = {
            ATTR_DEVICE: self.packet.device.name,
            ATTR_ROOM_ID: self.packet.room_id,
            ATTR_SUB_ID: self.packet.sub_id,
        }

    @property
    def available(self):
        """Return True if device is available."""
        return self.gateway.connected and self.packet.state

    async def async_send_packet(self, packet: bytes):
        """Send a packet to the client."""
        await self.gateway.async_send_wait(packet)

    async def async_added_to_hass(self) -> None:
        """Register state update callback."""

        @callback
        def async_update_packet(packet: ImazuPacket) -> None:
            """Handle packet updates."""
            if self.packet.state == packet.state:
                return
            self.packet = packet
            self.async_write_ha_state()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self.gateway.host}_{self.packet.device_id}",
                async_update_packet,
            )
        )

    @property
    def extra_restore_state_data(self) -> RestoredExtraData:
        """Return entity specific state data to be restored."""
        return RestoredExtraData({PACKET: self.packet.hex()})

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self) -> None:
        """Update device."""
        make_packet = self.packet.make_scan()
        await self.gateway.async_send(make_packet)
