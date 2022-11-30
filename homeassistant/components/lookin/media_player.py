"""The lookin integration light platform."""
from __future__ import annotations

import logging

from aiolookin import Remote

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, TYPE_TO_PLATFORM
from .coordinator import LookinDataUpdateCoordinator
from .entity import LookinPowerPushRemoteEntity
from .models import LookinData

LOGGER = logging.getLogger(__name__)

_TYPE_TO_DEVICE_CLASS = {
    "01": MediaPlayerDeviceClass.TV,
    "02": MediaPlayerDeviceClass.RECEIVER,
}

_FUNCTION_NAME_TO_FEATURE = {
    "power": MediaPlayerEntityFeature.TURN_OFF,
    "poweron": MediaPlayerEntityFeature.TURN_ON,
    "poweroff": MediaPlayerEntityFeature.TURN_OFF,
    "mute": MediaPlayerEntityFeature.VOLUME_MUTE,
    "volup": MediaPlayerEntityFeature.VOLUME_STEP,
    "chup": MediaPlayerEntityFeature.NEXT_TRACK,
    "chdown": MediaPlayerEntityFeature.PREVIOUS_TRACK,
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
        if TYPE_TO_PLATFORM.get(remote["Type"]) != Platform.MEDIA_PLAYER:
            continue
        uuid = remote["UUID"]
        coordinator = lookin_data.device_coordinators[uuid]
        device: Remote = coordinator.data
        entities.append(
            LookinMedia(
                coordinator=coordinator,
                uuid=uuid,
                device=device,
                lookin_data=lookin_data,
                device_class=_TYPE_TO_DEVICE_CLASS[remote["Type"]],
            )
        )

    async_add_entities(entities)


class LookinMedia(LookinPowerPushRemoteEntity, MediaPlayerEntity):
    """A lookin media player."""

    _attr_should_poll = False

    def __init__(
        self,
        coordinator: LookinDataUpdateCoordinator,
        uuid: str,
        device: Remote,
        lookin_data: LookinData,
        device_class: str,
    ) -> None:
        """Init the lookin media player."""
        self._attr_device_class = device_class
        super().__init__(coordinator, uuid, device, lookin_data)
        for function_name, feature in _FUNCTION_NAME_TO_FEATURE.items():
            if function_name in self._function_names:
                self._attr_supported_features |= feature

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
        self._attr_is_volume_muted = not self.is_volume_muted
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        """Turn the media player off."""
        await self._async_send_command(self._power_off_command)
        self._attr_state = MediaPlayerState.STANDBY
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        """Turn the media player on."""
        await self._async_send_command(self._power_on_command)
        self._attr_state = MediaPlayerState.ON
        self.async_write_ha_state()

    def _update_from_status(self, status: str) -> None:
        """Update media property from status.

        00F0
        0 - 0/1 on/off
        0 - sourse
        F - volume, 0 - muted, 1 - volume up, F - volume down
        0 - not used
        """
        if len(status) != 4:
            return
        state = status[0]
        mute = status[2]

        self._attr_state = (
            MediaPlayerState.ON if state == "1" else MediaPlayerState.STANDBY
        )
        self._attr_is_volume_muted = mute == "0"
