"""The lookin integration light platform."""
from __future__ import annotations

from homeassistant.components.media_player import (
    DEVICE_CLASS_RECEIVER,
    DEVICE_CLASS_TV,
    MediaPlayerEntity,
)
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

from .aiolookin import Remote
from .const import DOMAIN
from .entity import LookinPowerEntity
from .models import LookinData

_TYPE_TO_DEVICE_CLASS = {"01": DEVICE_CLASS_TV, "02": DEVICE_CLASS_RECEIVER}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    lookin_data: LookinData = hass.data[DOMAIN][config_entry.entry_id]

    entities = []

    for remote in lookin_data.devices:
        if remote["Type"] not in _TYPE_TO_DEVICE_CLASS:
            continue
        uuid = remote["UUID"]
        device = await lookin_data.lookin_protocol.get_remote(uuid)
        entities.append(
            LookinMedia(
                uuid=uuid,
                device=device,
                lookin_data=lookin_data,
                device_class=_TYPE_TO_DEVICE_CLASS[remote["Type"]],
            )
        )

    async_add_entities(entities, update_before_add=True)


class LookinMedia(LookinPowerEntity, MediaPlayerEntity):
    _attr_should_poll = False

    def __init__(
        self,
        uuid: str,
        device: Remote,
        lookin_data: LookinData,
        device_class: str,
    ) -> None:
        super().__init__(uuid, device, lookin_data)
        self._attr_device_class = device_class
        self._supported_features: int = 0
        self._state: str = STATE_PLAYING
        for function in self._device.functions:
            if function.name == "power":
                self._attr_supported_features |= SUPPORT_TURN_OFF
            elif function.name == "poweron":
                self._attr_supported_features |= SUPPORT_TURN_ON
            elif function.name == "poweroff":
                self._attr_supported_features |= SUPPORT_TURN_OFF
            elif function.name == "mute":
                self._attr_supported_features |= SUPPORT_VOLUME_MUTE
            elif function.name == "volup":
                self._attr_supported_features |= SUPPORT_VOLUME_STEP
            elif function.name == "chup":
                self._attr_supported_features |= SUPPORT_NEXT_TRACK
            elif function.name == "chdown":
                self._attr_supported_features |= SUPPORT_PREVIOUS_TRACK

    @property
    def state(self) -> str:
        return self._state

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
