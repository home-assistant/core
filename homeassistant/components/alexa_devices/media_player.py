"""Media player platform for Alexa Devices."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

from aioamazondevices.structures import (
    AmazonMediaControls,
    AmazonMediaState,
    AmazonVolumeState,
)

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEnqueue,
    MediaPlayerEntity,
    MediaPlayerEntityDescription,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import _LOGGER
from .coordinator import AmazonConfigEntry, AmazonDevicesCoordinator
from .entity import AmazonEntity
from .utils import alexa_api_call

PARALLEL_UPDATES = 1

STANDARD_SUPPORTED_FEATURES = (
    MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.PLAY_MEDIA
)


@dataclass(frozen=True, kw_only=True)
class AmazonDevicesMediaPlayerEntityDescription(MediaPlayerEntityDescription):
    """Describes an Alexa Devices media player entity."""


MEDIA_PLAYERS: Final = (
    AmazonDevicesMediaPlayerEntityDescription(
        key="media",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AmazonConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Alexa Devices media player entities from a config entry."""
    coordinator = entry.runtime_data

    known_devices: set[str] = set()

    def _check_device() -> None:
        """Add entities for newly discovered devices."""
        new_entities: list[AlexaDevicesMediaPlayer] = []

        for serial_num, device in coordinator.data.items():
            if serial_num in known_devices or not device.media_player_supported:
                continue

            known_devices.add(serial_num)
            new_entities.extend(
                AlexaDevicesMediaPlayer(coordinator, serial_num, description)
                for description in MEDIA_PLAYERS
            )

        if new_entities:
            async_add_entities(new_entities)

    remove_listener = coordinator.async_add_listener(_check_device)
    entry.async_on_unload(remove_listener)
    _check_device()


class AlexaDevicesMediaPlayer(AmazonEntity, MediaPlayerEntity):
    """Representation of an Alexa device media player."""

    entity_description: AmazonDevicesMediaPlayerEntityDescription

    _attr_has_entity_name = True
    _attr_name = None  # Uses the device name
    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_volume_step = 0.05

    def __init__(
        self,
        coordinator: AmazonDevicesCoordinator,
        serial_num: str,
        description: AmazonDevicesMediaPlayerEntityDescription,
    ) -> None:
        """Initialize."""
        self._prev_volume: int | None = None
        super().__init__(coordinator, serial_num, description)

    @property
    def media_state(self) -> AmazonMediaState | None:
        """Return the media state relating to device."""
        if not self.coordinator or not self.coordinator.media_states:
            return None
        return self.coordinator.media_states.get(self._serial_num)

    @property
    def volume_state(self) -> AmazonVolumeState | None:
        """Volume settings for device."""
        if not self.coordinator or not self.coordinator.volume_states:
            return None
        return self.coordinator.volume_states.get(self._serial_num)

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Return dynamically supported features based on current media."""
        features = STANDARD_SUPPORTED_FEATURES

        if self.media_state is None:
            return features

        if self.media_state.pause_enabled:
            features |= MediaPlayerEntityFeature.PLAY | MediaPlayerEntityFeature.PAUSE

        if self.media_state.next_enabled:
            features |= MediaPlayerEntityFeature.NEXT_TRACK

        if self.media_state.previous_enabled:
            features |= MediaPlayerEntityFeature.PREVIOUS_TRACK

        return features

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the current state of the player."""
        if not self.media_state:
            return MediaPlayerState.IDLE
        if self.media_state.player_state == "PLAYING":
            return MediaPlayerState.PLAYING
        if self.media_state.player_state == "PAUSED":
            return MediaPlayerState.PAUSED

        return MediaPlayerState.IDLE

    @property
    def volume_level(self) -> float | None:
        """Return the volume level (0.0 to 1.0)."""
        if not self.volume_state or self.volume_state.volume is None:
            return None
        return self.volume_state.volume / 100

    @property
    def is_volume_muted(self) -> bool | None:
        """Return True if the volume is muted."""
        if not self.volume_state:
            return None
        return self.volume_state.volume == 0

    @property
    def media_title(self) -> str | None:
        """Track title."""
        if not self.media_state:
            return None
        return self.media_state.now_playing_title

    @property
    def media_artist(self) -> str | None:
        """Artist name."""
        if not self.media_state:
            return None
        return self.media_state.now_playing_line1

    @property
    def media_album_name(self) -> str | None:
        """Album name."""
        if not self.media_state:
            return None
        return self.media_state.now_playing_line2

    @property
    def media_image_url(self) -> str | None:
        """Album art URL."""
        if not self.media_state:
            return None
        return self.media_state.now_playing_url

    @property
    def media_duration(self) -> int | None:
        """Duration in seconds."""
        if not self.media_state:
            return None
        return self.media_state.media_length

    @property
    def media_position(self) -> int | None:
        """Current playback position in seconds."""
        if not self.media_state:
            return None
        return self.media_state.media_position

    @property
    def media_position_updated_at(self) -> datetime | None:
        """When media_position was last updated — HA uses this to interpolate the progress bar."""
        if not self.media_state:
            return None
        return self.media_state.media_position_updated_at

    @property
    def media_content_type(self) -> MediaType | None:
        """Content type — tells HA what kind of media is playing."""
        if self.state in [MediaPlayerState.PLAYING, MediaPlayerState.PAUSED]:
            return MediaType.MUSIC
        return None

    async def async_play_media(
        self,
        media_type: MediaType | str,
        media_id: str,
        enqueue: MediaPlayerEnqueue | None = None,
        announce: bool | None = None,
        **kwargs: Any,
    ) -> None:
        """Play a piece of media."""
        await self.async_call_alexa_music(media_id, media_type)

    @alexa_api_call
    async def async_call_alexa_music(self, search_term: str, provider: str) -> None:
        """Call alexa music."""
        await self.coordinator.api.call_alexa_music(self.device, search_term, provider)

    @alexa_api_call
    async def async_set_device_volume(self, volume: int) -> None:
        """Set the device volume."""
        _LOGGER.debug(
            "Setting volume for %s to %s%%",
            self.device.serial_number,
            volume,
        )
        await self.coordinator.api.set_device_volume(self.device, volume)

    async def async_set_volume_level(self, volume: float) -> None:
        """Set the volume level (0.0 to 1.0)."""
        device_volume = round(volume * 100)
        await self.async_set_device_volume(device_volume)

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or un-mute the volume."""
        # Whilst you can mute a device by asking it there appears to be
        # no way to do this programmatically so set volume to 0
        if not self.volume_state or self.volume_state.volume is None:
            return
        if mute:
            self._prev_volume = self.volume_state.volume
            target_volume = 0
        else:
            if self._prev_volume is None:
                return
            target_volume = self._prev_volume
        await self.async_set_volume_level(target_volume / 100)

    @alexa_api_call
    async def _send_media_command(self, command: AmazonMediaControls) -> None:
        _LOGGER.debug(
            "Sending media command '%s' to %s", command, self.device.serial_number
        )
        await self.coordinator.api.send_media_command(self.device, command)

    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self._send_media_command(AmazonMediaControls.Stop)

    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self._send_media_command(AmazonMediaControls.Pause)

    async def async_media_play(self) -> None:
        """Send play command."""
        await self._send_media_command(AmazonMediaControls.Play)

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self._send_media_command(AmazonMediaControls.Next)

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self._send_media_command(AmazonMediaControls.Previous)
