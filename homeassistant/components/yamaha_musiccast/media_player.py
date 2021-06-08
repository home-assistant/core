"""Demo implementation of the media player."""
from __future__ import annotations

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import (
    REPEAT_MODE_OFF,
    SUPPORT_CLEAR_PLAYLIST,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_REPEAT_SET,
    SUPPORT_SELECT_SOUND_MODE,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_SHUFFLE_SET,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_IDLE, STATE_OFF, STATE_PAUSED, STATE_PLAYING
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import HomeAssistantType

from . import MusicCastDataUpdateCoordinator, MusicCastDeviceEntity
from .const import (
    DEFAULT_ZONE,
    DOMAIN,
    HA_REPEAT_MODE_TO_MC_MAPPING,
    MC_REPEAT_MODE_TO_HA_MAPPING,
)

PARALLEL_UPDATES = 1


MUSIC_PLAYER_SUPPORT = (
    SUPPORT_PAUSE
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_CLEAR_PLAYLIST
    | SUPPORT_PLAY
    | SUPPORT_SHUFFLE_SET
    | SUPPORT_REPEAT_SET
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_SELECT_SOUND_MODE
    | SUPPORT_SELECT_SOURCE
    | SUPPORT_STOP
)


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up MusicCast sensor based on a config entry."""
    coordinator: MusicCastDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    name = coordinator.data.network_name

    media_players: list[Entity] = []

    for zone in coordinator.data.zones:
        zone_name = name if zone == DEFAULT_ZONE else f"{name} {zone}"

        media_players.append(
            MusicCastMediaPlayer(zone, zone_name, entry.entry_id, coordinator)
        )

    async_add_entities(media_players)


class MusicCastMediaPlayer(MusicCastDeviceEntity, MediaPlayerEntity):
    """The musiccast media player."""

    def __init__(self, zone_id, name, entry_id, coordinator):
        """Initialize the musiccast device."""
        self._player_state = STATE_PLAYING
        self._volume_muted = False
        self._shuffle = False
        self._zone_id = zone_id
        self.coordinator: MusicCastDataUpdateCoordinator = coordinator

        self._volume_min = self.coordinator.data.zones[self._zone_id].min_volume
        self._volume_max = self.coordinator.data.zones[self._zone_id].max_volume

        self._cur_track = 0
        self._repeat = REPEAT_MODE_OFF

        super().__init__(
            entry_id=entry_id,
            name=name,
            icon="mdi:speaker",
        )

    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        await super().async_added_to_hass()
        # Sensors should also register callbacks to HA when their state changes
        self.coordinator.musiccast.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        await super().async_will_remove_from_hass()
        # The opposite of async_added_to_hass. Remove any registered call backs here.
        self.coordinator.musiccast.remove_callback(self.async_write_ha_state)

    @property
    def zone_id(self):
        """Return the zone_id of the media_player."""
        return self._zone_id

    @property
    def ip_address(self):
        """Return the ip address of the musiccast device."""
        return self.coordinator.musiccast.ip

    @property
    def should_poll(self):
        """Push an update after each command."""
        return False

    @property
    def _is_netusb(self):
        return (
            self.coordinator.data.netusb_input
            == self.coordinator.data.zones[self._zone_id].input
        )

    @property
    def _is_tuner(self):
        return self.coordinator.data.zones[self._zone_id].input == "tuner"

    @property
    def state(self):
        """Return the state of the player."""
        if self.coordinator.data.zones[self._zone_id].power == "on":
            if self._is_netusb and self.coordinator.data.netusb_playback == "pause":
                return STATE_PAUSED
            if self._is_netusb and self.coordinator.data.netusb_playback == "stop":
                return STATE_IDLE
            return STATE_PLAYING
        return STATE_OFF

    @property
    def volume_level(self):
        """Return the volume level of the media player (0..1)."""
        volume = self.coordinator.data.zones[self._zone_id].current_volume
        return (volume - self._volume_min) / (self._volume_max - self._volume_min)

    @property
    def is_volume_muted(self):
        """Return boolean if volume is currently muted."""
        return self.coordinator.data.zones[self._zone_id].mute

    @property
    def shuffle(self):
        """Boolean if shuffling is enabled."""
        return (
            self.coordinator.data.netusb_shuffle == "on" if self._is_netusb else False
        )

    @property
    def sound_mode(self):
        """Return the current sound mode."""
        return self.coordinator.data.zones[self._zone_id].sound_program

    @property
    def sound_mode_list(self):
        """Return a list of available sound modes."""
        return self.coordinator.data.zones[self._zone_id].sound_program_list

    @property
    def zone(self):
        """Return the zone of the media player."""
        return self._zone_id

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this media_player."""
        macs = self.coordinator.data.mac_addresses
        return f"{macs}_{self._zone_id}"

    async def async_turn_on(self):
        """Turn the media player on."""
        await self.coordinator.musiccast.turn_on(self._zone_id)
        self.async_write_ha_state()

    async def async_turn_off(self):
        """Turn the media player off."""
        await self.coordinator.musiccast.turn_off(self._zone_id)
        self.schedule_update_ha_state()

    async def async_mute_volume(self, mute):
        """Mute the volume."""

        await self.coordinator.musiccast.mute_volume(self._zone_id, mute)
        self.schedule_update_ha_state()

    async def async_set_volume_level(self, volume):
        """Set the volume level, range 0..1."""
        await self.coordinator.musiccast.set_volume_level(self._zone_id, volume)
        self.schedule_update_ha_state()

    async def async_media_play(self):
        """Send play command."""
        if self._is_netusb:
            await self.coordinator.musiccast.netusb_play()

    async def async_media_pause(self):
        """Send pause command."""
        if self._is_netusb:
            await self.coordinator.musiccast.netusb_pause()

    async def async_media_stop(self):
        """Send stop command."""
        if self._is_netusb:
            await self.coordinator.musiccast.netusb_pause()

    async def async_set_shuffle(self, shuffle):
        """Enable/disable shuffle mode."""
        if self._is_netusb:
            await self.coordinator.musiccast.netusb_shuffle(shuffle)

    async def async_select_sound_mode(self, sound_mode):
        """Select sound mode."""
        await self.coordinator.musiccast.select_sound_mode(self._zone_id, sound_mode)

    @property
    def media_image_url(self):
        """Return the image url of current playing media."""
        return self.coordinator.musiccast.media_image_url if self._is_netusb else None

    @property
    def media_title(self):
        """Return the title of current playing media."""
        if self._is_netusb:
            return self.coordinator.data.netusb_track
        if self._is_tuner:
            return self.coordinator.musiccast.tuner_media_title

        return None

    @property
    def media_artist(self):
        """Return the artist of current playing media (Music track only)."""
        if self._is_netusb:
            return self.coordinator.data.netusb_artist
        if self._is_tuner:
            return self.coordinator.musiccast.tuner_media_artist

        return None

    @property
    def media_album_name(self):
        """Return the album of current playing media (Music track only)."""
        return self.coordinator.data.netusb_album if self._is_netusb else None

    @property
    def repeat(self):
        """Return current repeat mode."""
        return (
            MC_REPEAT_MODE_TO_HA_MAPPING.get(self.coordinator.data.netusb_repeat)
            if self._is_netusb
            else REPEAT_MODE_OFF
        )

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return MUSIC_PLAYER_SUPPORT

    async def async_media_previous_track(self):
        """Send previous track command."""
        if self._is_netusb:
            await self.coordinator.musiccast.netusb_previous_track()
        elif self._is_tuner:
            await self.coordinator.musiccast.tuner_previous_station()

    async def async_media_next_track(self):
        """Send next track command."""
        if self._is_netusb:
            await self.coordinator.musiccast.netusb_next_track()
        elif self._is_tuner:
            await self.coordinator.musiccast.tuner_next_station()

    def clear_playlist(self):
        """Clear players playlist."""
        self._cur_track = 0
        self._player_state = STATE_OFF
        self.schedule_update_ha_state()

    async def async_set_repeat(self, repeat):
        """Enable/disable repeat mode."""
        if self._is_netusb:
            await self.coordinator.musiccast.netusb_repeat(
                HA_REPEAT_MODE_TO_MC_MAPPING.get(repeat, "off")
            )

    async def async_select_source(self, source):
        """Select input source."""
        await self.coordinator.musiccast.select_source(self._zone_id, source)

    @property
    def source(self):
        """Name of the current input source."""
        return self.coordinator.data.zones[self._zone_id].input

    @property
    def source_list(self):
        """List of available input sources."""
        return self.coordinator.data.zones[self._zone_id].input_list

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        if self._is_netusb:
            return self.coordinator.data.netusb_total_time

        return None

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        if self._is_netusb:
            return self.coordinator.data.netusb_play_time

        return None

    @property
    def media_position_updated_at(self):
        """When was the position of the current playing media valid.

        Returns value from homeassistant.util.dt.utcnow().
        """
        if self._is_netusb:
            return self.coordinator.data.netusb_play_time_updated

        return None
