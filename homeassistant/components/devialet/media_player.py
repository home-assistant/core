"""Support for Devialet speakers."""

from __future__ import annotations

from devialet.const import NORMAL_INPUTS

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, SOUND_MODES
from .coordinator import DevialetCoordinator

SUPPORT_DEVIALET = (
    MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.SELECT_SOUND_MODE
)

DEVIALET_TO_HA_FEATURE_MAP = {
    "play": MediaPlayerEntityFeature.PLAY | MediaPlayerEntityFeature.STOP,
    "pause": MediaPlayerEntityFeature.PAUSE,
    "previous": MediaPlayerEntityFeature.PREVIOUS_TRACK,
    "next": MediaPlayerEntityFeature.NEXT_TRACK,
    "seek": MediaPlayerEntityFeature.SEEK,
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the Devialet entry."""
    client = hass.data[DOMAIN][entry.entry_id]
    coordinator = DevialetCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    async_add_entities([DevialetMediaPlayerEntity(coordinator, entry)])


class DevialetMediaPlayerEntity(
    CoordinatorEntity[DevialetCoordinator], MediaPlayerEntity
):
    """Devialet media player."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, coordinator: DevialetCoordinator, entry: ConfigEntry) -> None:
        """Initialize the Devialet device."""
        self.coordinator = coordinator
        super().__init__(coordinator)

        self._attr_unique_id = str(entry.unique_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            manufacturer=MANUFACTURER,
            model=self.coordinator.client.model,
            name=entry.data[CONF_NAME],
            sw_version=self.coordinator.client.version,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if not self.coordinator.client.is_available:
            self.async_write_ha_state()
            return

        self._attr_volume_level = self.coordinator.client.volume_level
        self._attr_is_volume_muted = self.coordinator.client.is_volume_muted
        self._attr_source_list = self.coordinator.client.source_list
        self._attr_sound_mode_list = sorted(SOUND_MODES)
        self._attr_media_artist = self.coordinator.client.media_artist
        self._attr_media_album_name = self.coordinator.client.media_album_name
        self._attr_media_artist = self.coordinator.client.media_artist
        self._attr_media_image_url = self.coordinator.client.media_image_url
        self._attr_media_duration = self.coordinator.client.media_duration
        self._attr_media_position = self.coordinator.client.current_position
        self._attr_media_position_updated_at = (
            self.coordinator.client.position_updated_at
        )
        self._attr_media_title = (
            self.coordinator.client.media_title
            if self.coordinator.client.media_title
            else self.source
        )
        self.async_write_ha_state()

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the device."""
        playing_state = self.coordinator.client.playing_state

        if not playing_state:
            return MediaPlayerState.IDLE
        if playing_state == "playing":
            return MediaPlayerState.PLAYING
        if playing_state == "paused":
            return MediaPlayerState.PAUSED
        return MediaPlayerState.ON

    @property
    def available(self) -> bool:
        """Return if the media player is available."""
        return self.coordinator.client.is_available

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Flag media player features that are supported."""
        features = SUPPORT_DEVIALET

        if self.coordinator.client.source_state is None:
            return features

        if not self.coordinator.client.available_options:
            return features

        for option in self.coordinator.client.available_options:
            features |= DEVIALET_TO_HA_FEATURE_MAP.get(option, 0)
        return features

    @property
    def source(self) -> str | None:
        """Return the current input source."""
        source = self.coordinator.client.source

        for pretty_name, name in NORMAL_INPUTS.items():
            if source == name:
                return pretty_name
        return None

    @property
    def sound_mode(self) -> str | None:
        """Return the current sound mode."""
        if self.coordinator.client.equalizer is not None:
            sound_mode = self.coordinator.client.equalizer
        elif self.coordinator.client.night_mode:
            sound_mode = "night mode"
        else:
            return None

        for pretty_name, mode in SOUND_MODES.items():
            if sound_mode == mode:
                return pretty_name
        return None

    async def async_volume_up(self) -> None:
        """Volume up media player."""
        await self.coordinator.client.async_volume_up()

    async def async_volume_down(self) -> None:
        """Volume down media player."""
        await self.coordinator.client.async_volume_down()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self.coordinator.client.async_set_volume_level(volume)

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute (true) or unmute (false) media player."""
        await self.coordinator.client.async_mute_volume(mute)

    async def async_media_play(self) -> None:
        """Play media player."""
        await self.coordinator.client.async_media_play()

    async def async_media_pause(self) -> None:
        """Pause media player."""
        await self.coordinator.client.async_media_pause()

    async def async_media_stop(self) -> None:
        """Pause media player."""
        await self.coordinator.client.async_media_stop()

    async def async_media_next_track(self) -> None:
        """Send the next track command."""
        await self.coordinator.client.async_media_next_track()

    async def async_media_previous_track(self) -> None:
        """Send the previous track command."""
        await self.coordinator.client.async_media_previous_track()

    async def async_media_seek(self, position: float) -> None:
        """Send seek command."""
        await self.coordinator.client.async_media_seek(position)

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        """Send sound mode command."""
        for pretty_name, mode in SOUND_MODES.items():
            if sound_mode == pretty_name:
                if mode == "night mode":
                    await self.coordinator.client.async_set_night_mode(True)
                else:
                    await self.coordinator.client.async_set_night_mode(False)
                    await self.coordinator.client.async_set_equalizer(mode)

    async def async_turn_off(self) -> None:
        """Turn off media player."""
        await self.coordinator.client.async_turn_off()

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        await self.coordinator.client.async_select_source(source)
