"""Support for Devialet Phantom speakers."""
from __future__ import annotations

import datetime
from datetime import timedelta

from devialet import DevialetApi
from devialet.const import NORMAL_INPUTS

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, MANUFACTURER, SOUND_MODES

SCAN_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)

SUPPORT_DEVIALET = (
    MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.SELECT_SOUND_MODE
)

SUPPORT_MEDIA_MODES = (
    MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.SEEK
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Devialet entry."""
    client = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [DevialetDevice(client, entry)],
        update_before_add=True,
    )


class DevialetDevice(MediaPlayerEntity):
    """Representation of a Devialet device."""

    def __init__(self, client: DevialetApi, entry: ConfigEntry) -> None:
        """Initialize the Devialet device."""
        self._client = client
        self._name = entry.data[CONF_NAME]
        self._muted = False
        if entry.unique_id:
            self._serial = entry.unique_id

    async def async_update(self) -> None:
        """Get the latest details from the device."""
        await self._client.async_update()

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._serial)},
            name=self._name,
            manufacturer=MANUFACTURER,
            model=self._client.model,
            sw_version=self._client.version,
        )

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique id of the device."""
        return self._serial

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the device."""
        if not self._client.is_available:
            return MediaPlayerState.OFF

        playing_state = self._client.playing_state

        if not playing_state:
            return MediaPlayerState.IDLE
        if playing_state == "playing":
            return MediaPlayerState.PLAYING
        if playing_state == "paused":
            return MediaPlayerState.PAUSED
        return MediaPlayerState.ON

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        return self._client.volume_level

    @property
    def is_volume_muted(self) -> bool | None:
        """Return boolean if volume is currently muted."""
        return self._client.is_volume_muted

    @property
    def source_list(self) -> list[str] | None:
        """Return the list of available input sources."""
        return self._client.source_list

    @property
    def sound_mode_list(self) -> list[str] | None:
        """Return the list of available sound modes."""
        return sorted(SOUND_MODES)

    @property
    def media_artist(self) -> str | None:
        """Artist of current playing media, music track only."""
        return self._client.media_artist

    @property
    def media_album_name(self) -> str | None:
        """Album name of current playing media, music track only."""
        return self._client.media_album_name

    @property
    def media_title(self) -> str | None:
        """Return the current media info."""
        if not self._client.media_title:
            return self.source

        return self._client.media_title

    @property
    def media_image_url(self) -> str | None:
        """Image url of current playing media."""
        return self._client.media_image_url

    @property
    def media_duration(self) -> int | None:
        """Duration of current playing media in seconds."""
        return self._client.media_duration

    @property
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        return self._client.current_position

    @property
    def media_position_updated_at(self) -> datetime.datetime | None:
        """When was the position of the current playing media valid."""
        return self._client.position_updated_at

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        features = SUPPORT_DEVIALET

        if self._client.source_state is None:
            return features

        available_options = self._client.available_options
        if available_options is None:
            return features

        if "play" in available_options:
            features = features | MediaPlayerEntityFeature.PLAY
        if "pause" in available_options:
            features = (
                features
                | MediaPlayerEntityFeature.PAUSE
                | MediaPlayerEntityFeature.STOP
            )
        if "previous" in available_options:
            features = features | MediaPlayerEntityFeature.PREVIOUS_TRACK
        if "next" in available_options:
            features = features | MediaPlayerEntityFeature.NEXT_TRACK
        if "seek" in available_options:
            features = features | MediaPlayerEntityFeature.SEEK
        return features

    @property
    def source(self) -> str | None:
        """Return the current input source."""
        source = self._client.source

        for pretty_name, name in NORMAL_INPUTS.items():
            if source == name:
                return pretty_name
        return None

    @property
    def sound_mode(self) -> str | None:
        """Return the current sound mode."""
        if self._client.equalizer is not None:
            sound_mode = self._client.equalizer
        elif self._client.night_mode:
            sound_mode = "night mode"
        else:
            return None

        for pretty_name, mode in SOUND_MODES.items():
            if sound_mode == mode:
                return pretty_name
        return None

    async def async_volume_up(self) -> None:
        """Volume up media player."""
        await self._client.async_volume_up()

    async def async_volume_down(self) -> None:
        """Volume down media player."""
        await self._client.async_volume_down()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self._client.async_set_volume_level(volume)

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) media player."""
        await self._client.async_mute_volume(mute)

    async def async_media_play(self) -> None:
        """Play media player."""
        await self._client.async_media_play()

    async def async_media_pause(self) -> None:
        """Pause media player."""
        await self._client.async_media_pause()

    async def async_media_stop(self) -> None:
        """Pause media player."""
        await self._client.async_media_stop()

    async def async_media_next_track(self) -> None:
        """Send the next track command."""
        await self._client.async_media_next_track()

    async def async_media_previous_track(self) -> None:
        """Send the previous track command."""
        await self._client.async_media_previous_track()

    async def async_media_seek(self, position: float) -> None:
        """Send seek command."""
        await self._client.async_media_seek(position)

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Send sound mode command."""
        for pretty_name, mode in SOUND_MODES.items():
            if sound_mode == pretty_name:
                if mode == "night mode":
                    await self._client.async_set_night_mode(True)
                else:
                    await self._client.async_set_night_mode(False)
                    await self._client.async_set_equalizer(mode)

    async def async_turn_off(self) -> None:
        """Turn off media player."""
        await self._client.async_turn_off()

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        await self._client.async_select_source(source)
