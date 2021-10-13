"""The lookin integration light platform."""
from __future__ import annotations

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import (
    SUPPORT_NEXT_TRACK,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_PLAYING
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import LookinPowerEntity
from .const import DEVICES, DOMAIN, LOOKIN_DEVICE, PROTOCOL
from .models import Device, Remote
from .protocol import LookInHttpProtocol


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][config_entry.entry_id]
    lookin_device = data[LOOKIN_DEVICE]
    lookin_protocol = data[PROTOCOL]
    devices = data[DEVICES]

    entities = []

    for remote in devices:
        if remote["Type"] in ("01", "02"):
            uuid = remote["UUID"]
            device = await lookin_protocol.get_remote(uuid)
            device_class = "tv" if remote["Type"] == "01" else "media"
            entities.append(
                LookinMedia(
                    uuid=uuid,
                    lookin_protocol=lookin_protocol,
                    device_class=device_class,
                    device=device,
                    lookin_device=lookin_device,
                )
            )

    async_add_entities(entities, update_before_add=True)


class LookinMedia(LookinPowerEntity, MediaPlayerEntity):
    _attr_should_poll = False

    def __init__(
        self,
        uuid: str,
        lookin_protocol: LookInHttpProtocol,
        device_class: str,
        device: Remote,
        lookin_device: Device,
    ) -> None:
        super().__init__(uuid, lookin_protocol, device, lookin_device)
        self._device_class = device_class
        self._supported_features: int = 0
        self._state: str = STATE_PLAYING

        for function in self._device.functions:
            if function.name == "power":
                self._supported_features = (
                    self._supported_features | SUPPORT_TURN_ON | SUPPORT_TURN_OFF
                )
            elif function.name == "poweron":
                self._supported_features = self._supported_features | SUPPORT_TURN_ON
            elif function.name == "poweroff":
                self._supported_features = self._supported_features | SUPPORT_TURN_OFF
            elif function.name == "mute":
                self._supported_features = (
                    self._supported_features | SUPPORT_VOLUME_MUTE
                )
            elif function.name == "volup":
                self._supported_features = (
                    self._supported_features | SUPPORT_VOLUME_STEP
                )
            elif function.name == "chup":
                self._supported_features = self._supported_features | SUPPORT_NEXT_TRACK
            elif function.name == "chdown":
                self._supported_features = (
                    self._supported_features | SUPPORT_PREVIOUS_TRACK
                )

    @property
    def state(self) -> str:
        return self._state

    @property
    def device_class(self) -> str:
        return self._device_class

    @property
    def supported_features(self) -> int:
        return self._supported_features

    async def async_volume_up(self) -> None:
        await self._lookin_protocol.send_command(
            uuid=self._uuid, command="volup", signal="FF"
        )

    async def async_volume_down(self) -> None:
        await self._lookin_protocol.send_command(
            uuid=self._uuid, command="voldown", signal="FF"
        )

    async def async_media_previous_track(self) -> None:
        await self._lookin_protocol.send_command(
            uuid=self._uuid, command="chdown", signal="FF"
        )

    async def async_media_next_track(self) -> None:
        await self._lookin_protocol.send_command(
            uuid=self._uuid, command="chup", signal="FF"
        )

    async def async_mute_volume(self, mute: bool) -> None:
        await self._lookin_protocol.send_command(
            uuid=self._uuid, command="mute", signal="FF"
        )

    async def async_turn_off(self) -> None:
        await self._lookin_protocol.send_command(
            uuid=self._uuid, command=self._power_off_command, signal="FF"
        )

    async def async_turn_on(self) -> None:
        await self._lookin_protocol.send_command(
            uuid=self._uuid, command=self._power_on_command, signal="FF"
        )
