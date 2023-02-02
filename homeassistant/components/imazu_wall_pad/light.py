"""Light platform for Imazu Wall Pad integration."""
from typing import Any

from wp_imazu.packet import LightPacket

from homeassistant import config_entries
from homeassistant.components.light import LightEntity
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ImazuGateway
from .const import DOMAIN
from .gateway import EntityData
from .wall_pad import WallPadDevice

SCAN_LIGHT_PACKETS = [
    "01190140100000",
    "01190140200000",
    "01190140300000",
    "01190140400000",
    "01190140500000",
    "01190140600000",
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize Imazu Wall Pad config entry."""
    gateway: ImazuGateway = hass.data[DOMAIN].get(config_entry.entry_id)

    @callback
    def async_add_entity(data: EntityData):
        if isinstance(data.packet, LightPacket):
            data.device = WPLight(gateway, Platform.LIGHT, data.packet)

        if data.device:
            async_add_entities([data.device])

    entities = gateway.get_platform_entities(Platform.LIGHT)
    for data in entities:
        async_add_entity(data)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass, gateway.entity_add_signal(Platform.LIGHT), async_add_entity
        )
    )

    if len(entities) == 0:
        for packet in SCAN_LIGHT_PACKETS:
            await gateway.async_send(bytes.fromhex(packet))


class WPLight(WallPadDevice[LightPacket], LightEntity):
    """Representation of a Wall Pad light."""

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self.packet.state["power"] == LightPacket.Power.ON

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on light."""
        make_packet = self.packet.make_change_power(LightPacket.Power.ON)
        await super().async_send_packet(make_packet)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off light."""
        make_packet = self.packet.make_change_power(LightPacket.Power.OFF)
        await super().async_send_packet(make_packet)
