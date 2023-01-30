"""Fan platform for Imazu Wall Pad integration."""
from typing import Any

from wp_imazu.packet import FanPacket

from homeassistant import config_entries
from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from . import ImazuGateway
from .const import DOMAIN
from .gateway import EntityData
from .wall_pad import WallPadDevice

SCAN_FAN_PACKET = ["012b0140110000"]

MODE_OFF = "Off"
MODE_AUTO = "Auto"
MODE_MANUAL = "Manual"
FAN_SPEED_LIST = [
    FanPacket.Speed.LOW,
    FanPacket.Speed.MEDIUM,
    FanPacket.Speed.HIGH,
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
        if data.device:
            return

        if isinstance(data.packet, FanPacket):
            data.device = WPFan(gateway.client, Platform.FAN, data.packet)

        if data.device:
            async_add_entities([data.device])

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass, gateway.entity_add_signal(Platform.FAN), async_add_entity
        )
    )

    if not gateway.add_platform_entities(Platform.FAN):
        for packet in SCAN_FAN_PACKET:
            await gateway.client.async_send(bytes.fromhex(packet))


class WPFan(WallPadDevice[FanPacket], FanEntity):
    """Representation of a Wall Pad fan."""

    _attr_speed_count = 3
    _attr_preset_modes = [MODE_OFF, MODE_AUTO, MODE_MANUAL]

    @property
    def is_on(self) -> bool:
        """Return true if fan is on."""
        if not self.available:
            return False
        mode: FanPacket.Mode = self.packet.state["mode"]
        return mode != FanPacket.Mode.OFF

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if not self.available:
            return 0

        mode: FanPacket.Mode = self.packet.state["mode"]
        if mode != FanPacket.Mode.MANUAL:
            return 0

        speed: FanPacket.Speed = self.packet.state["speed"]
        if speed == FanPacket.Speed.OFF:
            return 0

        return ordered_list_item_to_percentage(FAN_SPEED_LIST, speed)

    @property
    def preset_mode(self) -> str:
        """Return the preset mode."""
        if not self.available:
            return MODE_OFF

        mode: FanPacket.Mode = self.packet.state["mode"]
        if mode == FanPacket.Mode.AUTO:
            return MODE_AUTO
        if mode == FanPacket.Mode.MANUAL:
            return MODE_MANUAL
        return MODE_OFF

    @property
    def supported_features(self) -> FanEntityFeature:
        """Flag supported features."""
        features = FanEntityFeature.PRESET_MODE
        if self.preset_mode == MODE_MANUAL:
            features |= FanEntityFeature.SET_SPEED
        return features

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed percentage of the fan."""
        speed = (
            percentage_to_ordered_list_item(FAN_SPEED_LIST, percentage)
            if percentage > 0
            else FanPacket.Speed.OFF
        )
        make_packet = self.packet.make_change_speed(speed)
        await super().async_send_packet(make_packet)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of the fan."""
        if preset_mode == MODE_AUTO:
            make_packet = self.packet.make_change_mode(FanPacket.Mode.AUTO)
        elif preset_mode == MODE_MANUAL:
            make_packet = self.packet.make_change_mode(FanPacket.Mode.MANUAL)
        else:
            make_packet = self.packet.make_change_mode(FanPacket.Mode.OFF)
        await super().async_send_packet(make_packet)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        if not preset_mode:
            await self.async_set_preset_mode(MODE_AUTO)
            return
        if preset_mode == MODE_OFF:
            return
        await self.async_set_preset_mode(preset_mode)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off fan."""
        await self.async_set_preset_mode(MODE_OFF)
