"""Media player platform for Lyngdorf integration."""

from __future__ import annotations

from lyngdorf.device import Receiver

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import LyngdorfEntity
from .models import LyngdorfConfigEntry

PARALLEL_UPDATES = 1

MAX_VOLUME_DB = 18.0
MIN_VOLUME_DB = -80.0
VOLUME_RANGE = MAX_VOLUME_DB - MIN_VOLUME_DB

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


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LyngdorfConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the receiver from a config entry."""
    client = config_entry.runtime_data.receiver
    device_info = config_entry.runtime_data.device_info

    async_add_entities(
        [
            LyngdorfMainDevice(client, config_entry, device_info),
            LyngdorfZoneBDevice(client, config_entry, device_info),
        ]
    )


def _to_ha_volume(volume_db: float) -> float:
    """Convert Lyngdorf dB volume to HA 0..1 scale, clamped to 0..1."""
    volume = (volume_db - MIN_VOLUME_DB) / VOLUME_RANGE
    return max(0.0, min(volume, 1.0))


def _to_lyngdorf_volume(volume: float) -> float:
    """Convert HA 0..1 volume to Lyngdorf dB scale, clamped to min and max."""
    volume_db = volume * VOLUME_RANGE + MIN_VOLUME_DB
    return max(MIN_VOLUME_DB, min(volume_db, MAX_VOLUME_DB))


class LyngdorfDevice(LyngdorfEntity, MediaPlayerEntity):
    """Base Lyngdorf media player entity."""

    _attr_device_class = MediaPlayerDeviceClass.RECEIVER

    def __init__(
        self,
        receiver: Receiver,
        config_entry: LyngdorfConfigEntry,
        device_info: DeviceInfo,
        translation_key: str,
        entity_id_suffix: str,
        features: MediaPlayerEntityFeature = MediaPlayerEntityFeature(0),
    ) -> None:
        """Initialize the device."""
        super().__init__(receiver)
        assert config_entry.unique_id
        self._attr_device_info = device_info
        self._attr_unique_id = f"{config_entry.unique_id}_{entity_id_suffix}"
        self._attr_translation_key = translation_key
        self._attr_supported_features = features


class LyngdorfZoneBDevice(LyngdorfDevice):
    """Lyngdorf Zone B device."""

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
            "zone_b",
            "zone_b",
            FEATURES_ZONE_B,
        )

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the device."""
        if self._receiver.zone_b_power_on:
            return MediaPlayerState.ON
        return MediaPlayerState.OFF

    @property
    def is_volume_muted(self) -> bool | None:
        """Return boolean if volume is currently muted."""
        return self._receiver.zone_b_mute_enabled

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        if not isinstance(self._receiver.zone_b_volume, float):
            return None
        return _to_ha_volume(self._receiver.zone_b_volume)

    def turn_on(self) -> None:
        """Turn on media player."""
        self._receiver.zone_b_power_on = True

    def turn_off(self) -> None:
        """Turn off media player."""
        self._receiver.zone_b_power_on = False

    def volume_up(self) -> None:
        """Volume up the media player."""
        self._receiver.zone_b_volume_up()

    def volume_down(self) -> None:
        """Volume down the media player."""
        self._receiver.zone_b_volume_down()

    def set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        self._receiver.zone_b_volume = _to_lyngdorf_volume(volume)

    def mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        self._receiver.zone_b_mute_enabled = mute

    @property
    def source(self) -> str | None:
        """Return the current input source."""
        return self._receiver.zone_b_source

    @property
    def source_list(self) -> list[str] | None:
        """Return the list of available sources."""
        return self._receiver.zone_b_available_sources

    def select_source(self, source: str) -> None:
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
            FEATURES_MAIN,
        )

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the device."""
        if self._receiver.power_on:
            if self._playing_audio or self._playing_video:
                return MediaPlayerState.PLAYING
            return MediaPlayerState.ON
        return MediaPlayerState.OFF

    @property
    def media_title(self) -> str | None:
        """Return title of the current media."""
        if self.state != MediaPlayerState.PLAYING:
            return None

        parts: list[str] = []
        if self._playing_audio:
            parts.append(f"audio: {self._receiver.audio_information}")
        if self._playing_video:
            parts.append(f"video: {self._receiver.video_information}")

        return " ".join(parts) if parts else None

    @property
    def _playing_video(self) -> bool:
        """Return whether video is playing."""
        return bool(
            self._receiver.video_information
            and not self._receiver.video_information.startswith("No")
        )

    @property
    def _playing_audio(self) -> bool:
        """Return whether audio is playing."""
        return bool(
            self._receiver.audio_information
            and not self._receiver.audio_information.startswith("No")
        )

    @property
    def media_content_type(self) -> MediaType | None:
        """Return the content type of the current media."""
        if self.state != MediaPlayerState.PLAYING:
            return None
        if self._playing_video:
            return MediaType.VIDEO
        if self._playing_audio:
            return MediaType.MUSIC
        return None

    @property
    def source_list(self) -> list[str] | None:
        """Return a list of available input sources."""
        return self._receiver.available_sources

    @property
    def sound_mode_list(self) -> list[str] | None:
        """Return a list of available sound modes."""
        return self._receiver.available_sound_modes

    @property
    def is_volume_muted(self) -> bool | None:
        """Return boolean if volume is currently muted."""
        return self._receiver.mute_enabled

    @property
    def volume_level(self) -> float | None:
        """Volume level of the media player (0..1)."""
        if not isinstance(self._receiver.volume, float):
            return None
        return _to_ha_volume(self._receiver.volume)

    @property
    def source(self) -> str | None:
        """Return the current input source."""
        return self._receiver.source

    @property
    def sound_mode(self) -> str | None:
        """Return the current sound mode."""
        return self._receiver.sound_mode

    def turn_on(self) -> None:
        """Turn on media player."""
        self._receiver.power_on = True

    def turn_off(self) -> None:
        """Turn off media player."""
        self._receiver.power_on = False

    def volume_up(self) -> None:
        """Volume up the media player."""
        self._receiver.volume_up()

    def volume_down(self) -> None:
        """Volume down the media player."""
        self._receiver.volume_down()

    def set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        self._receiver.volume = _to_lyngdorf_volume(volume)

    def mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        self._receiver.mute_enabled = mute

    def select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode."""
        self._receiver.sound_mode = sound_mode

    def select_source(self, source: str) -> None:
        """Select input source."""
        self._receiver.source = source
