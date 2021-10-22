"""The lookin integration light platform."""
from __future__ import annotations

from aiolookin import Remote

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

from .const import DOMAIN
from .entity import LookinPowerEntity
from .models import LookinData

_TYPE_TO_DEVICE_CLASS = {"01": DEVICE_CLASS_TV, "02": DEVICE_CLASS_RECEIVER}

_FUNCTION_NAME_TO_FEATURE = {
    "power": SUPPORT_TURN_OFF,
    "poweron": SUPPORT_TURN_ON,
    "poweroff": SUPPORT_TURN_OFF,
    "mute": SUPPORT_VOLUME_MUTE,
    "volup": SUPPORT_VOLUME_STEP,
    "chup": SUPPORT_NEXT_TRACK,
    "chdown": SUPPORT_PREVIOUS_TRACK,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the media_player platform for lookin from a config entry."""
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

    async_add_entities(entities)


class LookinMedia(LookinPowerEntity, MediaPlayerEntity):
    """A lookin media player."""

    _attr_should_poll = False

    def __init__(
        self,
        uuid: str,
        device: Remote,
        lookin_data: LookinData,
        device_class: str,
    ) -> None:
        """Init the lookin media player."""
        super().__init__(uuid, device, lookin_data)
        self._attr_device_class = device_class
        self._attr_supported_features: int = 0
        self._state: str = STATE_PLAYING
        for function_name, feature in _FUNCTION_NAME_TO_FEATURE.items():
            if function_name in self._function_names:
                self._attr_supported_features |= feature

    @property
    def state(self) -> str:
        """State of the player."""
        return self._state

    async def async_volume_up(self) -> None:
        """Turn volume up for media player."""
        await self._async_send_command("volup")

    async def async_volume_down(self) -> None:
        """Turn volume down for media player."""
        await self._async_send_command("voldown")

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self._async_send_command("chdown")

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self._async_send_command("chup")

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        await self._async_send_command("mute")

    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        await self._async_send_command(self._power_off_command)

    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        await self._async_send_command(self._power_on_command)
