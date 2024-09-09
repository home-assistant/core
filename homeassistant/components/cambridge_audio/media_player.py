"""Support for Cambridge Audio AV Receiver."""

from __future__ import annotations

import datetime as dt

import homeassistant.util.dt as dte

from aiostreammagic import StreamMagicClient

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_BUFFERING, STATE_STANDBY,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from tests.components.mobile_app.test_webhook import homeassistant

from .entity import CambridgeAudioEntity

FEATURES = (
    MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.SHUFFLE_SET
    | MediaPlayerEntityFeature.REPEAT_SET
    | MediaPlayerEntityFeature.SEEK
)

BASE_FEATURES = (
    MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.TURN_ON
)

FEATURES_PREAMP = FEATURES | (
    MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.VOLUME_SET
)


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

    _attr_media_content_type = MediaType.MUSIC

    def __init__(self, client: StreamMagicClient) -> None:
        """Initialize an Cambridge Audio entity."""
        super().__init__(client)
        self._attr_unique_id = client.info.unit_id

    async def _callback_handler(self, _client: StreamMagicClient):
        self.schedule_update_ha_state()
        # print(self.client.position_last_updated, self.client.play_state.position, self.client.play_state.metadata.duration)
        print(self.client.play_state.state)

    async def async_added_to_hass(self) -> None:
        """Register callback handlers."""
        await self.client.register_state_update_callbacks(self._callback_handler)

    async def async_will_remove_from_hass(self) -> None:
        """Remove callbacks."""
        await self.client.unregister_state_update_callbacks(self._callback_handler)

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        title = self.client.play_state.metadata.title or ""
        controls = self.client.now_playing.controls
        print(self.client.now_playing.controls)
        features = BASE_FEATURES
        if "play_pause" in controls:
            features |= MediaPlayerEntityFeature.PLAY | MediaPlayerEntityFeature.PAUSE
        elif "play" in controls:
            features |= MediaPlayerEntityFeature.PLAY
        elif "pause" in controls:
            features |= MediaPlayerEntityFeature.PAUSE

        if "track_next" in controls:
            features |= MediaPlayerEntityFeature.NEXT_TRACK
        if "track_previous" in controls:
            features |= MediaPlayerEntityFeature.PREVIOUS_TRACK

        return features
        # if self.client.state.pre_amp_mode:
        #     return FEATURES_PREAMP
        # return FEATURES

    @property
    def state(self):
        """Return the state of the device."""
        media_state = self.client.play_state.state
        if media_state == "NETWORK":
            return STATE_STANDBY
        if self.client.state.power:
            if media_state == "play":
                return STATE_PLAYING
            if media_state == "pause":
                return STATE_PAUSED
            if media_state == "connecting":
                return STATE_BUFFERING
            if media_state == "stop" or media_state == "ready":
                return STATE_IDLE
            return STATE_ON
        return STATE_OFF

    @property
    def source_list(self):
        """Return a list of available input sources."""
        return [item.name for item in self.client.sources]

    @property
    def source(self):
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
    def media_artist(self):
        """Artist of current playing media, music track only."""
        return self.client.play_state.metadata.artist

    @property
    def media_album_name(self):
        """Album name of current playing media, music track only."""
        return self.client.play_state.metadata.album

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        return self.client.play_state.metadata.art_url

    @property
    def is_volume_muted(self):
        """Return boolean if volume is currently muted."""
        return self.client.state.mute

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        volume_percent = self.client.state.volume_percent
        if volume_percent is None:
            return None
        return float(volume_percent) / 100

    @property
    def media_duration(self) -> int | None:
        return self.client.play_state.metadata.duration

    @property
    def media_position(self) -> int | None:
        return self.client.play_state.position

    @property
    def media_position_updated_at(self) -> dt.datetime | None:
        dte.utcnow()
        return self.client.position_last_updated

    @property
    def shuffle(self) -> bool:
        return self.client.play_state.mode_shuffle != "off"

    @property
    def repeat(self) -> str:
        return self.client.play_state.mode_repeat

    # async def async_set_shuffle(self, shuffle: bool) -> None:
    #     """Set the shuffle mode of the media player."""
    #     shuffle_action = "off"
    #     if shuffle:
    #         shuffle_action = "all"
    #     await self.coordinator.client.set_shuffle(shuffle_action)
    #
    # async def async_set_repeat(self, repeat: RepeatMode) -> None:
    #     """Set the repeat mode of the media plyer."""
    #     repeat_action = repeat.title()
    #     if repeat == RepeatMode.ONE:
    #         repeat_action = "toggle"
    #
    #     await self.coordinator.client.set_repeat(repeat_action)

    async def async_media_play_pause(self) -> None:
        await self.client.play_pause()

    async def async_media_pause(self) -> None:
        controls = self.client.now_playing.controls
        if "pause" not in controls and "play_pause" in controls:
            await self.client.play_pause()
        else:
            await self.client.pause()

    async def async_media_stop(self) -> None:
        await self.client.stop()

    async def async_media_play(self) -> None:
        if self.state == STATE_PAUSED:
            await self.client.play_pause()

    async def async_media_next_track(self) -> None:
        await self.client.next_track()

    async def async_media_previous_track(self) -> None:
        await self.client.previous_track()

    # async def async_mute_volume(self, mute: bool) -> None:
    #     if mute:
    #         await self.coordinator.client.mute()
    #     else:
    #         await self.coordinator.client.unmute()

    async def async_select_source(self, source: str) -> None:
        for src in self.client.sources:
            if src.name == source:
                await self.client.set_source_by_id(src.id)
                break

    # async def async_set_volume_level(self, volume: float) -> None:
    #     await self.coordinator.client.set_volume(int(volume * 100))
    #
    # async def async_media_seek(self, position: float) -> None:
    #     await self.coordinator.client.media_seek(int(position))
    #
    # async def async_volume_up(self) -> None:
    #     await self.coordinator.client.volume_up()
    #
    # async def async_volume_down(self) -> None:
    #     await self.coordinator.client.volume_down()

    async def async_turn_on(self) -> None:
        await self.client.power_on()

    async def async_turn_off(self) -> None:
        await self.client.power_off()
