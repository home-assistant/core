"""Support for Cambridge Audio AV Receiver."""

from __future__ import annotations

from datetime import datetime

from aiostreammagic import StreamMagicClient

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import CambridgeAudioEntity

BASE_FEATURES = (
    MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.TURN_ON
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

    _attr_name = None
    _attr_media_content_type = MediaType.MUSIC

    def __init__(self, client: StreamMagicClient) -> None:
        """Initialize an Cambridge Audio entity."""
        super().__init__(client)
        self._attr_unique_id = client.info.unit_id

    async def _state_update_callback(self, _client: StreamMagicClient) -> None:
        """Call when the device is notified of changes."""
        self.schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callback handlers."""
        await self.client.register_state_update_callbacks(self._state_update_callback)

    async def async_will_remove_from_hass(self) -> None:
        """Remove callbacks."""
        await self.client.unregister_state_update_callbacks(self._state_update_callback)

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Supported features for the media player."""
        controls = self.client.now_playing.controls
        features = BASE_FEATURES
        if "play_pause" in controls:
            features |= MediaPlayerEntityFeature.PLAY | MediaPlayerEntityFeature.PAUSE
        if "play" in controls:
            features |= MediaPlayerEntityFeature.PLAY
        if "pause" in controls:
            features |= MediaPlayerEntityFeature.PAUSE
        if "track_next" in controls:
            features |= MediaPlayerEntityFeature.NEXT_TRACK
        if "track_previous" in controls:
            features |= MediaPlayerEntityFeature.PREVIOUS_TRACK
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

    async def async_media_play_pause(self) -> None:
        """Toggle play/pause the current media."""
        await self.client.play_pause()

    async def async_media_pause(self) -> None:
        """Pause the current media."""
        controls = self.client.now_playing.controls
        if "pause" not in controls and "play_pause" in controls:
            await self.client.play_pause()
        else:
            await self.client.pause()

    async def async_media_stop(self) -> None:
        """Stop the current media."""
        await self.client.stop()

    async def async_media_play(self) -> None:
        """Play the current media."""
        if self.state == MediaPlayerState.PAUSED:
            await self.client.play_pause()

    async def async_media_next_track(self) -> None:
        """Skip to the next track."""
        await self.client.next_track()

    async def async_media_previous_track(self) -> None:
        """Skip to the previous track."""
        await self.client.previous_track()

    async def async_select_source(self, source: str) -> None:
        """Select the source."""
        for src in self.client.sources:
            if src.name == source:
                await self.client.set_source_by_id(src.id)
                break

    async def async_turn_on(self) -> None:
        """Power on the device."""
        await self.client.power_on()

    async def async_turn_off(self) -> None:
        """Power off the device."""
        await self.client.power_off()
