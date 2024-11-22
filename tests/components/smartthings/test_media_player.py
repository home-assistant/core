"""Test for the SmartThings media_player platform."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pysmartthings import Capability, DeviceEntity

from homeassistant.components.media_player import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    RepeatMode,
)
from homeassistant.components.smartthings.const import DATA_BROKERS, DOMAIN
from homeassistant.components.smartthings.entity import SmartThingsEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

VALUE_TO_STATE = {
    "buffering": MediaPlayerState.BUFFERING,
    "pause": MediaPlayerState.PAUSED,
    "paused": MediaPlayerState.PAUSED,
    "play": MediaPlayerState.PLAYING,
    "playing": MediaPlayerState.PLAYING,
    "stop": MediaPlayerState.IDLE,
    "stopped": MediaPlayerState.IDLE,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add media players for a config entry."""
    broker = hass.data[DOMAIN][DATA_BROKERS][config_entry.entry_id]
    async_add_entities(
        [
            SmartThingsMediaPlayer(device)
            for device in broker.devices.values()
            if broker.any_assigned(device.device_id, MEDIA_PLAYER_DOMAIN)
        ]
    )


def get_capabilities(capabilities: Sequence[str]) -> Sequence[str] | None:
    """Return all capabilities supported if minimum required are present."""
    supported = [
        Capability.audio_mute,
        Capability.audio_volume,
        Capability.media_input_source,
        Capability.media_playback,
        Capability.media_playback_repeat,
        Capability.media_playback_shuffle,
        Capability.switch,
    ]
    # Must have one of these.
    media_player_capabilities = [
        Capability.audio_mute,
        Capability.audio_volume,
        Capability.media_input_source,
        Capability.media_playback,
        Capability.media_playback_repeat,
        Capability.media_playback_shuffle,
    ]
    if any(capability in capabilities for capability in media_player_capabilities):
        return supported
    return None


class SmartThingsMediaPlayer(SmartThingsEntity, MediaPlayerEntity):
    """Define a SmartThings media player."""

    def __init__(self, device: DeviceEntity) -> None:
        """Initialize the media_player class."""
        super().__init__(device)
        self._state = None
        self._state_attrs = None
        self._supported_features = (
            MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.STOP
        )
        if Capability.audio_volume in device.capabilities:
            self._supported_features |= (
                MediaPlayerEntityFeature.VOLUME_SET
                | MediaPlayerEntityFeature.VOLUME_STEP
            )
        if Capability.audio_mute in device.capabilities:
            self._supported_features |= MediaPlayerEntityFeature.VOLUME_MUTE
        if Capability.switch in device.capabilities:
            self._supported_features |= (
                MediaPlayerEntityFeature.TURN_ON | MediaPlayerEntityFeature.TURN_OFF
            )
        if Capability.media_input_source in device.capabilities:
            self._supported_features |= MediaPlayerEntityFeature.SELECT_SOURCE
        if Capability.media_playback_shuffle in device.capabilities:
            self._supported_features |= MediaPlayerEntityFeature.SHUFFLE_SET
        if Capability.media_playback_repeat in device.capabilities:
            self._supported_features |= MediaPlayerEntityFeature.REPEAT_SET

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the media player off."""
        await self._device.switch_off(set_status=True)
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the media player on."""
        await self._device.switch_on(set_status=True)
        self.async_write_ha_state()

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute volume."""
        if mute:
            await self._device.mute(set_status=True)
        else:
            await self._device.unmute(set_status=True)
        self.async_write_ha_state()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level."""
        await self._device.set_volume(int(volume * 100), set_status=True)
        self.async_write_ha_state()

    async def async_volume_up(self) -> None:
        """Increase volume."""
        await self._device.volume_up(set_status=True)
        self.async_write_ha_state()

    async def async_volume_down(self) -> None:
        """Decrease volume."""
        await self._device.volume_down(set_status=True)
        self.async_write_ha_state()

    async def async_media_play(self) -> None:
        """Play media."""
        await self._device.play(set_status=True)
        self.async_write_ha_state()

    async def async_media_pause(self) -> None:
        """Pause media."""
        await self._device.pause(set_status=True)
        self.async_write_ha_state()

    async def async_media_stop(self) -> None:
        """Stop media."""
        await self._device.stop(set_status=True)
        self.async_write_ha_state()

    async def async_select_source(self, source: str) -> None:
        """Select source."""
        await self._device.set_input_source(source, set_status=True)
        self.async_write_ha_state()

    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Set shuffle mode."""
        await self._device.set_playback_shuffle(shuffle, set_status=True)
        self.async_write_ha_state()

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode."""
        await self._device.set_repeat(repeat, set_status=True)
        self.async_write_ha_state()

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Supported features."""
        return self._supported_features

    @property
    def media_title(self) -> str | None:
        """Title of the current media."""
        return self._device.status.media_title

    @property
    def state(self) -> MediaPlayerState | None:
        """State of the media player."""
        if not self._device.status.switch:
            return MediaPlayerState.OFF
        if self._device.status.playback_status in VALUE_TO_STATE:
            return VALUE_TO_STATE[self._device.status.playback_status]
        return MediaPlayerState.ON

    @property
    def is_volume_muted(self) -> bool | None:
        """Returns if the volume is muted."""
        if self.supported_features & MediaPlayerEntityFeature.VOLUME_MUTE:
            return self._device.status.mute
        return None

    @property
    def volume_level(self) -> float | None:
        """Volume level."""
        if self.supported_features & MediaPlayerEntityFeature.VOLUME_SET:
            return self._device.status.volume / 100
        return None

    @property
    def source(self) -> str | None:
        """Input source."""
        if self.supported_features & MediaPlayerEntityFeature.SELECT_SOURCE:
            return self._device.status.input_source
        return None

    @property
    def source_list(self) -> list[str] | None:
        """List of input sources."""
        if self.supported_features & MediaPlayerEntityFeature.SELECT_SOURCE:
            return self._device.status.supported_input_sources
        return None

    @property
    def shuffle(self) -> bool | None:
        """Returns if shuffle mode is set."""
        if self.supported_features & MediaPlayerEntityFeature.SHUFFLE_SET:
            return self._device.status.playback_shuffle
        return None

    @property
    def repeat(self) -> RepeatMode | None:
        """Returns if repeat mode is set."""
        if self.supported_features & MediaPlayerEntityFeature.REPEAT_SET:
            return self._device.status.playback_repeat_mode
        return None
