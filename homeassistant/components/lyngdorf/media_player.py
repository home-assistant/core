"""Media player platform for Lyngdorf integration."""

from datetime import datetime
from typing import TYPE_CHECKING, override

from lyngdorf.device import Receiver
from lyngdorf.models.base import NumericRange
from lyngdorf.states import Control, PlaybackState, Repeat
from lyngdorf.streaming import NowPlaying

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import LyngdorfEntity
from .models import LyngdorfConfigEntry

PARALLEL_UPDATES = 1

FEATURES_ZONE_B = (
    MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.SELECT_SOURCE
)

FEATURES_MAIN = (
    MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    | MediaPlayerEntityFeature.SELECT_SOURCE
)

# The streaming module advertises transport per source and it changes at
# runtime, so these are added to FEATURES_MAIN only while the device offers
# them: AirPlay has no seek, a stopped device offers nothing at all.
CONTROL_FEATURES: tuple[tuple[Control, MediaPlayerEntityFeature], ...] = (
    (Control.PAUSE, MediaPlayerEntityFeature.PAUSE),
    (Control.NEXT_TRACK, MediaPlayerEntityFeature.NEXT_TRACK),
    (Control.PREVIOUS_TRACK, MediaPlayerEntityFeature.PREVIOUS_TRACK),
    (Control.SEEK, MediaPlayerEntityFeature.SEEK),
)

REPEAT_MODES: dict[Repeat, RepeatMode] = {
    Repeat.OFF: RepeatMode.OFF,
    Repeat.ONE: RepeatMode.ONE,
    Repeat.ALL: RepeatMode.ALL,
}

LYNGDORF_REPEATS: dict[RepeatMode, Repeat] = {v: k for k, v in REPEAT_MODES.items()}

PLAYBACK_STATES: dict[PlaybackState, MediaPlayerState] = {
    PlaybackState.PLAYING: MediaPlayerState.PLAYING,
    PlaybackState.PAUSED: MediaPlayerState.PAUSED,
    PlaybackState.STOPPED: MediaPlayerState.IDLE,
    PlaybackState.TRANSITIONING: MediaPlayerState.BUFFERING,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LyngdorfConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the receiver from a config entry."""
    runtime_data = config_entry.runtime_data

    entities: list[LyngdorfDevice] = [
        LyngdorfMainDevice(
            runtime_data.receiver, config_entry, runtime_data.device_info
        )
    ]
    if runtime_data.zone_b_device_info is not None:
        entities.append(
            LyngdorfZoneBDevice(
                runtime_data.receiver, config_entry, runtime_data.zone_b_device_info
            )
        )

    async_add_entities(entities)


def _to_ha_volume(volume_db: float, volume_range: NumericRange) -> float:
    """Convert Lyngdorf dB volume to HA 0..1 scale, clamped to 0..1."""
    span = volume_range.max - volume_range.min
    return max(0.0, min((volume_db - volume_range.min) / span, 1.0))


def _to_lyngdorf_volume(volume: float, volume_range: NumericRange) -> float:
    """Convert HA 0..1 volume to Lyngdorf dB scale, clamped to min and max."""
    span = volume_range.max - volume_range.min
    volume_db = volume * span + volume_range.min
    return max(volume_range.min, min(volume_db, volume_range.max))


class LyngdorfDevice(LyngdorfEntity, MediaPlayerEntity):
    """Base Lyngdorf media player entity."""

    _attr_device_class = MediaPlayerDeviceClass.RECEIVER

    def __init__(
        self,
        receiver: Receiver,
        config_entry: LyngdorfConfigEntry,
        device_info: DeviceInfo,
        translation_key: str | None,
        entity_id_suffix: str,
    ) -> None:
        """Initialize the device."""
        super().__init__(receiver, device_info)
        if TYPE_CHECKING:
            assert config_entry.unique_id
        self._attr_unique_id = f"{config_entry.unique_id}_{entity_id_suffix}"
        self._attr_translation_key = translation_key


class LyngdorfZoneBDevice(LyngdorfDevice):
    """Lyngdorf Zone B device."""

    _attr_supported_features = FEATURES_ZONE_B

    def __init__(
        self,
        receiver: Receiver,
        config_entry: LyngdorfConfigEntry,
        device_info: DeviceInfo,
    ) -> None:
        """Create the device."""
        super().__init__(
            receiver,
            config_entry,
            device_info,
            None,
            "zone_b",
        )

    @override
    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the device."""
        if self._receiver.zone_b_power_on:
            return MediaPlayerState.ON
        return MediaPlayerState.OFF

    @override
    @property
    def is_volume_muted(self) -> bool | None:
        """Return boolean if volume is currently muted."""
        return self._receiver.zone_b_mute_enabled

    @property
    def _volume_range(self) -> NumericRange:
        """Return the model's documented Zone B volume range."""
        volume_range = self._receiver.zone_b_volume_range
        # This entity is only created for models that have a Zone B.
        if TYPE_CHECKING:
            assert volume_range is not None
        return volume_range

    @override
    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        if (volume := self._receiver.zone_b_volume) is None:
            return None
        return _to_ha_volume(volume, self._volume_range)

    @override
    async def async_turn_on(self) -> None:
        """Turn on media player."""
        self._receiver.zone_b_power_on = True

    @override
    async def async_turn_off(self) -> None:
        """Turn off media player."""
        self._receiver.zone_b_power_on = False

    @override
    async def async_volume_up(self) -> None:
        """Volume up the media player."""
        self._receiver.zone_b_volume_up()

    @override
    async def async_volume_down(self) -> None:
        """Volume down the media player."""
        self._receiver.zone_b_volume_down()

    @override
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        self._receiver.set_zone_b_volume(
            _to_lyngdorf_volume(volume, self._volume_range)
        )

    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        self._receiver.zone_b_mute_enabled = mute

    @override
    @property
    def source(self) -> str | None:
        """Return the current input source."""
        return self._receiver.zone_b_source

    @override
    @property
    def source_list(self) -> list[str] | None:
        """Return the list of available sources."""
        return self._receiver.zone_b_available_sources

    @override
    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        self._receiver.zone_b_source = source


class LyngdorfMainDevice(LyngdorfDevice):
    """Lyngdorf main zone device."""

    def __init__(
        self,
        receiver: Receiver,
        config_entry: LyngdorfConfigEntry,
        device_info: DeviceInfo,
    ) -> None:
        """Create the device."""
        super().__init__(
            receiver,
            config_entry,
            device_info,
            "main_zone",
            "main_zone",
        )

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to position discontinuities."""
        # The jump callback fires on a seek, track change, play/pause or
        # drift, rather than once a second, which is all Home Assistant
        # needs: it stores a position and a timestamp and extrapolates.
        await super().async_added_to_hass()
        if self._has_streamer:
            self.async_on_remove(
                self._receiver.register_position_jump_callback(self._handle_position)
            )

    @callback
    def _handle_position(self, _position_ms: int | None) -> None:
        """Handle a position discontinuity."""
        self.async_write_ha_state()

    @property
    def _has_streamer(self) -> bool:
        """Return whether this model has a streaming module at all."""
        return self._receiver.model.has_streaming_feature()

    @property
    def _now_playing(self) -> NowPlaying | None:
        """Return the current track, or None if this model has no streamer."""
        if not self._has_streamer:
            return None
        return self._receiver.now_playing

    @override
    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Return the features the device currently offers."""
        features = FEATURES_MAIN
        if (now_playing := self._now_playing) is None:
            return features

        for control, feature in CONTROL_FEATURES:
            if control in now_playing.controls:
                features |= feature
        if self._receiver.can_shuffle:
            features |= MediaPlayerEntityFeature.SHUFFLE_SET
        if self._receiver.available_repeat_modes:
            features |= MediaPlayerEntityFeature.REPEAT_SET
        return features

    @override
    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the device."""
        if not self._receiver.power_on:
            return MediaPlayerState.OFF
        if (now_playing := self._now_playing) is not None:
            if (state := PLAYBACK_STATES.get(now_playing.state)) is not None:
                return state
        return MediaPlayerState.ON

    @override
    @property
    def media_content_type(self) -> MediaType | None:
        """Return the type of media currently playing."""
        if self._now_playing is None:
            return None
        return MediaType.MUSIC

    @override
    @property
    def media_title(self) -> str | None:
        """Return the title of the current track."""
        return now_playing.title if (now_playing := self._now_playing) else None

    @override
    @property
    def media_artist(self) -> str | None:
        """Return the artist of the current track."""
        return now_playing.artist if (now_playing := self._now_playing) else None

    @override
    @property
    def media_album_name(self) -> str | None:
        """Return the album of the current track."""
        return now_playing.album if (now_playing := self._now_playing) else None

    @override
    @property
    def media_image_url(self) -> str | None:
        """Return the album art of the current track."""
        return now_playing.art_url if (now_playing := self._now_playing) else None

    @override
    @property
    def media_duration(self) -> int | None:
        """Return the duration of the current track, in seconds."""
        if (
            now_playing := self._now_playing
        ) is None or now_playing.duration_ms is None:
            return None
        return round(now_playing.duration_ms / 1000)

    @override
    @property
    def media_position(self) -> int | None:
        """Return the position of the current track, in seconds."""
        if not self._has_streamer or not self._receiver.has_position:
            return None
        return round(self._receiver.position_ms / 1000)

    @override
    @property
    def media_position_updated_at(self) -> datetime | None:
        """Return when the position was last valid."""
        if not self._has_streamer or not self._receiver.has_position:
            return None
        return self._receiver.position_updated_at

    @override
    @property
    def shuffle(self) -> bool | None:
        """Return whether shuffle is enabled."""
        return self._receiver.shuffle if self._has_streamer else None

    @override
    @property
    def repeat(self) -> RepeatMode | None:
        """Return the current repeat mode."""
        if not self._has_streamer or (repeat := self._receiver.repeat) is None:
            return None
        return REPEAT_MODES.get(repeat)

    @override
    async def async_media_pause(self) -> None:
        """Pause playback."""
        # On a controller-driven source such as AirPlay the device ends the
        # session rather than pausing, and only the controlling app can
        # start it again.
        await self._receiver.async_pause()

    @override
    async def async_media_next_track(self) -> None:
        """Skip to the next track."""
        await self._receiver.async_next()

    @override
    async def async_media_previous_track(self) -> None:
        """Skip to the previous track."""
        await self._receiver.async_previous()

    @override
    async def async_media_seek(self, position: float) -> None:
        """Seek to a position, given in seconds."""
        await self._receiver.async_seek(round(position * 1000))

    @override
    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Enable or disable shuffle, leaving the repeat mode alone."""
        await self._receiver.async_set_shuffle(shuffle)

    @override
    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set the repeat mode, leaving shuffle alone."""
        await self._receiver.async_set_repeat(LYNGDORF_REPEATS[repeat])

    @override
    @property
    def source_list(self) -> list[str] | None:
        """Return a list of available input sources."""
        return self._receiver.available_sources

    @override
    @property
    def sound_mode_list(self) -> list[str] | None:
        """Return a list of available sound modes."""
        return self._receiver.available_sound_modes

    @override
    @property
    def is_volume_muted(self) -> bool | None:
        """Return boolean if volume is currently muted."""
        return self._receiver.mute_enabled

    @property
    def _volume_range(self) -> NumericRange:
        """Return the model's documented main-zone volume range."""
        volume_range = self._receiver.volume_range
        # Every supported model documents a main-zone volume range.
        if TYPE_CHECKING:
            assert volume_range is not None
        return volume_range

    @override
    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        if (volume := self._receiver.volume) is None:
            return None
        return _to_ha_volume(volume, self._volume_range)

    @override
    @property
    def source(self) -> str | None:
        """Return the current input source."""
        return self._receiver.source

    @override
    @property
    def sound_mode(self) -> str | None:
        """Return the current sound mode."""
        return self._receiver.sound_mode

    @override
    async def async_turn_on(self) -> None:
        """Turn on media player."""
        self._receiver.power_on = True

    @override
    async def async_turn_off(self) -> None:
        """Turn off media player."""
        self._receiver.power_on = False

    @override
    async def async_volume_up(self) -> None:
        """Volume up the media player."""
        self._receiver.volume_up()

    @override
    async def async_volume_down(self) -> None:
        """Volume down the media player."""
        self._receiver.volume_down()

    @override
    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        self._receiver.set_volume(_to_lyngdorf_volume(volume, self._volume_range))

    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        self._receiver.mute_enabled = mute

    @override
    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode."""
        self._receiver.sound_mode = sound_mode

    @override
    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        self._receiver.source = source
