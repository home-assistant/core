"""Media player platform for Tesla Fleet integration."""

from __future__ import annotations

from tesla_fleet_api.const import Scope

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import TeslaFleetConfigEntry
from .entity import TeslaFleetVehicleEntity
from .helpers import handle_vehicle_command
from .models import TeslaFleetVehicleData

STATES = {
    "Playing": MediaPlayerState.PLAYING,
    "Paused": MediaPlayerState.PAUSED,
    "Stopped": MediaPlayerState.IDLE,
    "Off": MediaPlayerState.OFF,
}
VOLUME_MAX = 11.0
VOLUME_STEP = 1.0 / 3

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TeslaFleetConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Tesla Fleet Media platform from a config entry."""

    async_add_entities(
        TeslaFleetMediaEntity(vehicle, Scope.VEHICLE_CMDS in entry.runtime_data.scopes)
        for vehicle in entry.runtime_data.vehicles
    )


class TeslaFleetMediaEntity(TeslaFleetVehicleEntity, MediaPlayerEntity):
    """Vehicle media player class."""

    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_supported_features = (
        MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.VOLUME_SET
    )
    _volume_max: float = VOLUME_MAX

    def __init__(
        self,
        data: TeslaFleetVehicleData,
        scoped: bool,
    ) -> None:
        """Initialize the media player entity."""
        super().__init__(data, "media")
        self.scoped = scoped
        if not scoped:
            self._attr_supported_features = MediaPlayerEntityFeature(0)

    def _async_update_attrs(self) -> None:
        """Update entity attributes."""
        self._volume_max = (
            self.get("vehicle_state_media_info_audio_volume_max") or VOLUME_MAX
        )
        self._attr_state = STATES.get(
            self.get("vehicle_state_media_info_media_playback_status") or "Off",
        )
        self._attr_volume_step = (
            1.0
            / self._volume_max
            / (
                self.get("vehicle_state_media_info_audio_volume_increment")
                or VOLUME_STEP
            )
        )

        if volume := self.get("vehicle_state_media_info_audio_volume"):
            self._attr_volume_level = volume / self._volume_max
        else:
            self._attr_volume_level = None

        if duration := self.get("vehicle_state_media_info_now_playing_duration"):
            self._attr_media_duration = duration / 1000
        else:
            self._attr_media_duration = None

        if duration and (
            position := self.get("vehicle_state_media_info_now_playing_elapsed")
        ):
            self._attr_media_position = position / 1000
        else:
            self._attr_media_position = None

        self._attr_media_title = self.get("vehicle_state_media_info_now_playing_title")
        self._attr_media_artist = self.get(
            "vehicle_state_media_info_now_playing_artist"
        )
        self._attr_media_album_name = self.get(
            "vehicle_state_media_info_now_playing_album"
        )
        self._attr_media_playlist = self.get(
            "vehicle_state_media_info_now_playing_station"
        )
        self._attr_source = self.get("vehicle_state_media_info_now_playing_source")

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self.wake_up_if_asleep()
        await handle_vehicle_command(
            self.api.adjust_volume(int(volume * self._volume_max))
        )
        self._attr_volume_level = volume
        self.async_write_ha_state()

    async def async_media_play(self) -> None:
        """Send play command."""
        if self.state != MediaPlayerState.PLAYING:
            await self.wake_up_if_asleep()
            await handle_vehicle_command(self.api.media_toggle_playback())
            self._attr_state = MediaPlayerState.PLAYING
            self.async_write_ha_state()

    async def async_media_pause(self) -> None:
        """Send pause command."""
        if self.state == MediaPlayerState.PLAYING:
            await self.wake_up_if_asleep()
            await handle_vehicle_command(self.api.media_toggle_playback())
            self._attr_state = MediaPlayerState.PAUSED
            self.async_write_ha_state()

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        await self.wake_up_if_asleep()
        await handle_vehicle_command(self.api.media_next_track())

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        await self.wake_up_if_asleep()
        await handle_vehicle_command(self.api.media_prev_track())
