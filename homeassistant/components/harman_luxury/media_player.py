"""Media player platform for Harman Luxury."""

from datetime import datetime
from typing import override

from aioharmanluxury import HarmanLuxuryClient

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HarmanLuxuryConfigEntry, HarmanLuxuryCoordinator

# The device serializes control on a single session; serialize at HA's layer.
PARALLEL_UPDATES = 1

_PLAY_STATE_MAP = {
    "playing": MediaPlayerState.PLAYING,
    "paused": MediaPlayerState.PAUSED,
    "stopped": MediaPlayerState.IDLE,
    "buffering": MediaPlayerState.BUFFERING,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HarmanLuxuryConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the media player from a config entry."""
    async_add_entities([HarmanLuxuryMediaPlayer(entry.runtime_data)])


class HarmanLuxuryMediaPlayer(
    CoordinatorEntity[HarmanLuxuryCoordinator], MediaPlayerEntity
):
    """Representation of a Harman Luxury streamer."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    # The device volume is 0..99, so step by one native unit.
    _attr_volume_step = 1 / 99

    # Volume is always controllable. Transport availability is source-dependent
    # (Spotify Connect / AirPlay are sender-controlled), so it is advertised
    # dynamically from the device's own capability flags. Power is read-only on
    # this platform and therefore not exposed as a control.
    _BASE_FEATURES = (
        MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
    )

    def __init__(self, coordinator: HarmanLuxuryCoordinator) -> None:
        """Initialize the media player."""
        super().__init__(coordinator)
        info = coordinator.device_info
        self._attr_unique_id = info.serial
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, info.serial)},
            connections={(CONNECTION_NETWORK_MAC, info.mac)} if info.mac else set(),
            manufacturer="Harman Luxury Audio",
            model=info.model,
            name=info.name,
        )

    @property
    def _client(self) -> HarmanLuxuryClient:
        """Return the device client."""
        return self.coordinator.client

    @property
    @override
    def state(self) -> MediaPlayerState:
        """Return the state of the device."""
        data = self.coordinator.data
        if not data.online:
            return MediaPlayerState.OFF
        return _PLAY_STATE_MAP.get(data.play_state, MediaPlayerState.ON)

    @property
    @override
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Return the currently available features.

        Transport support is reported per-source by the device, so only the
        actions the active source actually allows are advertised.
        """
        features = self._BASE_FEATURES
        data = self.coordinator.data
        if data.play_state == "paused":
            features |= MediaPlayerEntityFeature.PLAY
        if data.can_pause:
            features |= MediaPlayerEntityFeature.PAUSE
        if data.play_state in ("playing", "paused"):
            features |= MediaPlayerEntityFeature.STOP
        if data.can_next:
            features |= MediaPlayerEntityFeature.NEXT_TRACK
        if data.can_previous:
            features |= MediaPlayerEntityFeature.PREVIOUS_TRACK
        return features

    @property
    @override
    def volume_level(self) -> float:
        """Return the volume level (0..1)."""
        return self.coordinator.data.volume / 99

    @property
    @override
    def is_volume_muted(self) -> bool:
        """Return whether the output is muted."""
        return self.coordinator.data.muted

    @property
    @override
    def media_title(self) -> str | None:
        """Return the title of the current media."""
        return self.coordinator.data.title

    @property
    @override
    def media_artist(self) -> str | None:
        """Return the artist of the current media."""
        return self.coordinator.data.artist

    @property
    @override
    def media_album_name(self) -> str | None:
        """Return the album of the current media."""
        return self.coordinator.data.album

    @property
    @override
    def media_image_url(self) -> str | None:
        """Return the album art URL."""
        return self.coordinator.data.art_url

    @property
    @override
    def media_duration(self) -> int | None:
        """Return the duration of the current media, in seconds."""
        duration = self.coordinator.data.duration
        return int(duration) if duration is not None else None

    @property
    @override
    def media_position(self) -> int | None:
        """Return the position of the current media, in seconds."""
        position = self.coordinator.data.position
        return int(position) if position is not None else None

    @property
    @override
    def media_position_updated_at(self) -> datetime | None:
        """Return when the media position was last retrieved."""
        return self.coordinator.position_updated_at

    @override
    async def async_set_volume_level(self, volume: float) -> None:
        """Set the volume level."""
        await self._client.async_set_volume(round(volume * 99))
        await self.coordinator.async_request_refresh()

    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute the output."""
        await self._client.async_set_mute(mute)
        await self.coordinator.async_request_refresh()

    @override
    async def async_media_play(self) -> None:
        """Resume playback."""
        await self._client.async_control("play")
        await self.coordinator.async_request_refresh()

    @override
    async def async_media_pause(self) -> None:
        """Pause playback."""
        await self._client.async_control("pause")
        await self.coordinator.async_request_refresh()

    @override
    async def async_media_stop(self) -> None:
        """Stop playback."""
        await self._client.async_control("stop")
        await self.coordinator.async_request_refresh()

    @override
    async def async_media_next_track(self) -> None:
        """Skip to the next track."""
        await self._client.async_control("next")
        await self.coordinator.async_request_refresh()

    @override
    async def async_media_previous_track(self) -> None:
        """Skip to the previous track."""
        await self._client.async_control("previous")
        await self.coordinator.async_request_refresh()
