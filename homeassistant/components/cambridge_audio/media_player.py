"""Support for Cambridge Audio AV Receiver."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from aiostreammagic import (
    RepeatMode as CambridgeRepeatMode,
    ShuffleMode,
    StreamMagicClient,
    TransportControl,
)

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CAMBRIDGE_MEDIA_TYPE_AIRABLE,
    CAMBRIDGE_MEDIA_TYPE_INTERNET_RADIO,
    CAMBRIDGE_MEDIA_TYPE_PRESET,
    DOMAIN,
)
from .entity import CambridgeAudioEntity, command

BASE_FEATURES = (
    MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.PLAY_MEDIA
)

PREAMP_FEATURES = (
    MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
)

TRANSPORT_FEATURES: dict[TransportControl, MediaPlayerEntityFeature] = {
    TransportControl.PLAY: MediaPlayerEntityFeature.PLAY,
    TransportControl.PAUSE: MediaPlayerEntityFeature.PAUSE,
    TransportControl.TRACK_NEXT: MediaPlayerEntityFeature.NEXT_TRACK,
    TransportControl.TRACK_PREVIOUS: MediaPlayerEntityFeature.PREVIOUS_TRACK,
    TransportControl.TOGGLE_REPEAT: MediaPlayerEntityFeature.REPEAT_SET,
    TransportControl.TOGGLE_SHUFFLE: MediaPlayerEntityFeature.SHUFFLE_SET,
    TransportControl.SEEK: MediaPlayerEntityFeature.SEEK,
    TransportControl.STOP: MediaPlayerEntityFeature.STOP,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Cambridge Audio device based on a config entry."""
    client: StreamMagicClient = entry.runtime_data
    async_add_entities([CambridgeAudioDevice(client)])


class CambridgeAudioDevice(CambridgeAudioEntity, MediaPlayerEntity):
    """Representation of a Cambridge Audio Media Player Device."""

    _attr_name = None
    _attr_media_content_type = MediaType.MUSIC
    _attr_device_class = MediaPlayerDeviceClass.RECEIVER

    def __init__(self, client: StreamMagicClient) -> None:
        """Initialize an Cambridge Audio entity."""
        super().__init__(client)
        self._attr_unique_id = client.info.unit_id

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Supported features for the media player."""
        controls = self.client.now_playing.controls
        features = BASE_FEATURES
        if self.client.state.pre_amp_mode:
            features |= PREAMP_FEATURES
        if TransportControl.PLAY_PAUSE in controls:
            features |= MediaPlayerEntityFeature.PLAY | MediaPlayerEntityFeature.PAUSE
        for control in controls:
            feature = TRANSPORT_FEATURES.get(control)
            if feature:
                features |= feature
        return features

    @property
    def state(self) -> MediaPlayerState:
        """Return the state of the device."""
        media_state = self.client.play_state.state
        if media_state == "NETWORK":
            return MediaPlayerState.STANDBY
        if self.client.state.power:
            if media_state == "play":
                return MediaPlayerState.PLAYING
            if media_state == "pause":
                return MediaPlayerState.PAUSED
            if media_state == "connecting":
                return MediaPlayerState.BUFFERING
            if media_state in ("stop", "ready"):
                return MediaPlayerState.IDLE
            return MediaPlayerState.ON
        return MediaPlayerState.OFF

    @property
    def source_list(self) -> list[str]:
        """Return a list of available input sources."""
        return [item.name for item in self.client.sources]

    @property
    def source(self) -> str | None:
        """Return the current input source."""
        return next(
            (
                item.name
                for item in self.client.sources
                if item.id == self.client.state.source
            ),
            None,
        )

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        return self.client.play_state.metadata.title

    @property
    def media_artist(self) -> str | None:
        """Artist of current playing media, music track only."""
        return self.client.play_state.metadata.artist

    @property
    def media_album_name(self) -> str | None:
        """Album name of current playing media, music track only."""
        return self.client.play_state.metadata.album

    @property
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""
        return self.client.play_state.metadata.art_url

    @property
    def media_duration(self) -> int | None:
        """Duration of the current media."""
        return self.client.play_state.metadata.duration

    @property
    def media_position(self) -> int | None:
        """Position of the current media."""
        return self.client.play_state.position

    @property
    def media_position_updated_at(self) -> datetime:
        """Last time the media position was updated."""
        return self.client.position_last_updated

    @property
    def is_volume_muted(self) -> bool | None:
        """Volume mute status."""
        return self.client.state.mute

    @property
    def volume_level(self) -> float | None:
        """Current pre-amp volume level."""
        volume = self.client.state.volume_percent or 0
        return volume / 100

    @property
    def shuffle(self) -> bool:
        """Current shuffle configuration."""
        return self.client.play_state.mode_shuffle != ShuffleMode.OFF

    @property
    def repeat(self) -> RepeatMode | None:
        """Current repeat configuration."""
        mode_repeat = RepeatMode.OFF
        if self.client.play_state.mode_repeat == CambridgeRepeatMode.ALL:
            mode_repeat = RepeatMode.ALL
        return mode_repeat

    @command
    async def async_media_play_pause(self) -> None:
        """Toggle play/pause the current media."""
        await self.client.play_pause()

    @command
    async def async_media_pause(self) -> None:
        """Pause the current media."""
        controls = self.client.now_playing.controls
        if (
            TransportControl.PAUSE not in controls
            and TransportControl.PLAY_PAUSE in controls
        ):
            await self.client.play_pause()
        else:
            await self.client.pause()

    @command
    async def async_media_stop(self) -> None:
        """Stop the current media."""
        await self.client.stop()

    @command
    async def async_media_play(self) -> None:
        """Play the current media."""
        controls = self.client.now_playing.controls
        if (
            TransportControl.PLAY not in controls
            and TransportControl.PLAY_PAUSE in controls
        ):
            await self.client.play_pause()
        else:
            await self.client.play()

    @command
    async def async_media_next_track(self) -> None:
        """Skip to the next track."""
        await self.client.next_track()

    @command
    async def async_media_previous_track(self) -> None:
        """Skip to the previous track."""
        await self.client.previous_track()

    @command
    async def async_select_source(self, source: str) -> None:
        """Select the source."""
        for src in self.client.sources:
            if src.name == source:
                await self.client.set_source_by_id(src.id)
                break

    @command
    async def async_turn_on(self) -> None:
        """Power on the device."""
        await self.client.power_on()

    @command
    async def async_turn_off(self) -> None:
        """Power off the device."""
        await self.client.power_off()

    @command
    async def async_volume_up(self) -> None:
        """Step the volume up."""
        await self.client.volume_up()

    @command
    async def async_volume_down(self) -> None:
        """Step the volume down."""
        await self.client.volume_down()

    @command
    async def async_set_volume_level(self, volume: float) -> None:
        """Set the volume level."""
        await self.client.set_volume(int(volume * 100))

    @command
    async def async_mute_volume(self, mute: bool) -> None:
        """Set the mute state."""
        await self.client.set_mute(mute)

    @command
    async def async_media_seek(self, position: float) -> None:
        """Seek to a position in the current media."""
        await self.client.media_seek(int(position))

    @command
    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Set the shuffle mode for the current queue."""
        shuffle_mode = ShuffleMode.OFF
        if shuffle:
            shuffle_mode = ShuffleMode.ALL
        await self.client.set_shuffle(shuffle_mode)

    @command
    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set the repeat mode for the current queue."""
        repeat_mode = CambridgeRepeatMode.OFF
        if repeat in {RepeatMode.ALL, RepeatMode.ONE}:
            repeat_mode = CambridgeRepeatMode.ALL
        await self.client.set_repeat(repeat_mode)

    @command
    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play media on the Cambridge Audio device."""

        if media_type not in {
            CAMBRIDGE_MEDIA_TYPE_PRESET,
            CAMBRIDGE_MEDIA_TYPE_AIRABLE,
            CAMBRIDGE_MEDIA_TYPE_INTERNET_RADIO,
        }:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unsupported_media_type",
                translation_placeholders={"media_type": media_type},
            )

        if media_type == CAMBRIDGE_MEDIA_TYPE_PRESET:
            try:
                preset_id = int(media_id)
            except ValueError as ve:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="preset_non_integer",
                    translation_placeholders={"preset_id": media_id},
                ) from ve
            preset = None
            for _preset in self.client.preset_list.presets:
                if _preset.preset_id == preset_id:
                    preset = _preset
            if not preset:
                raise ServiceValidationError(
                    translation_domain=DOMAIN,
                    translation_key="missing_preset",
                    translation_placeholders={"preset_id": media_id},
                )
            await self.client.recall_preset(preset.preset_id)

        if media_type == CAMBRIDGE_MEDIA_TYPE_AIRABLE:
            preset_id = int(media_id)
            await self.client.play_radio_airable("Radio", preset_id)

        if media_type == CAMBRIDGE_MEDIA_TYPE_INTERNET_RADIO:
            await self.client.play_radio_url("Radio", media_id)
