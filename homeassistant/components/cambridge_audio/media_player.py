"""Support for Cambridge Audio AV Receiver."""

from __future__ import annotations

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_IDLE,
    STATE_OFF,
    STATE_ON,
    STATE_PAUSED,
    STATE_PLAYING,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import CambridgeAudioCoordinator
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
    coordinator: CambridgeAudioCoordinator = entry.runtime_data
    async_add_entities([CambridgeAudioDevice(coordinator)])


class CambridgeAudioDevice(CambridgeAudioEntity, MediaPlayerEntity):
    """Representation of a Cambridge Audio Media Player Device."""

    def __init__(self, coordinator: CambridgeAudioCoordinator) -> None:
        """Initialize an Cambridge Audio entity."""
        super().__init__(coordinator)
        self._attr_unique_id = coordinator.data.info.unit_id
        if coordinator.data.state.pre_amp_mode:
            self._attr_supported_features = FEATURES_PREAMP
        else:
            self._attr_supported_features = FEATURES

    @property
    def state(self):
        """Return the state of the device."""
        media_state = self.coordinator.data.play_state.state
        if media_state == "NETWORK":
            return STATE_OFF
        if self.coordinator.data.state.power:
            if media_state == "play":
                return STATE_PLAYING
            if media_state == "pause":
                return STATE_PAUSED
            if media_state == "stop":
                return STATE_IDLE
            return STATE_ON
        return STATE_OFF

    @property
    def source_list(self):
        """Return a list of available input sources."""
        return [item.name for item in self.coordinator.data.sources]

    @property
    def source(self):
        """Return the current input source."""
        return next(
            (
                item.name
                for item in self.coordinator.data.sources
                if item.id == self.coordinator.data.state.source
            ),
            None,
        )

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        return self.coordinator.data.play_state.metadata.title

    @property
    def media_artist(self):
        """Artist of current playing media, music track only."""
        return self.coordinator.data.play_state.metadata.artist

    @property
    def media_album_name(self):
        """Album name of current playing media, music track only."""
        return self.coordinator.data.play_state.metadata.album

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        return self.coordinator.data.play_state.metadata.art_url

    @property
    def is_volume_muted(self):
        """Return boolean if volume is currently muted."""
        return self.coordinator.data.state.mute

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        volume_percent = self.coordinator.data.state.volume_percent
        if volume_percent is None:
            return None
        return float(volume_percent) / 100
