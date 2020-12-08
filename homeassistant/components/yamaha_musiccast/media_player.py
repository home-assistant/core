"""Demo implementation of the media player."""
from typing import Callable, List

from homeassistant.components.media_player import MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MUSIC,
    REPEAT_MODE_OFF,
    SUPPORT_CLEAR_PLAYLIST,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_REPEAT_SET,
    SUPPORT_SELECT_SOUND_MODE,
    SUPPORT_SHUFFLE_SET,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_PAUSED, STATE_PLAYING
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType
from pyamaha import Zone

from . import MusicCastDataUpdateCoordinator, MusicCastDeviceEntity
from .const import DOMAIN
from .musiccast_device import MusicCastData

PARALLEL_UPDATES = 1

DEFAULT_ZONE = "main"


async def async_setup_entry(
    hass: HomeAssistantType,
    entry: ConfigEntry,
    async_add_entities: Callable[[List[Entity], bool], None],
) -> None:
    """Set up MusicCast sensor based on a config entry."""
    coordinator: MusicCastDataUpdateCoordinator[MusicCastData] = hass.data[DOMAIN][
        entry.entry_id
    ]

    name = coordinator.data.network_name

    media_players = []

    for zone in coordinator.data.zones:
        zone_name = name if zone == DEFAULT_ZONE else f"{name} {zone}"

        media_players.append(
            MusicCastMediaPlayer(zone, zone_name, entry.entry_id, coordinator)
        )

    async_add_entities(media_players, True)


SOUND_MODE_LIST = ["Dummy Music", "Dummy Movie"]
DEFAULT_SOUND_MODE = "Dummy Music"


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
)


class MusicCastMediaPlayer(MediaPlayerEntity, MusicCastDeviceEntity):
    """A demo media players."""

    # We only implement the methods that we support

    tracks = [
        ("Technohead", "I Wanna Be A Hippy (Flamman & Abraxas Radio Mix)"),
        ("Paul Elstak", "Luv U More"),
        ("Dune", "Hardcore Vibes"),
        ("Nakatomi", "Children Of The Night"),
        ("Party Animals", "Have You Ever Been Mellow? (Flamman & Abraxas Radio Mix)"),
        ("Rob G.*", "Ecstasy, You Got What I Need"),
        ("Lipstick", "I'm A Raver"),
        ("4 Tune Fairytales", "My Little Fantasy (Radio Edit)"),
        ("Prophet", "The Big Boys Don't Cry"),
        ("Lovechild", "All Out Of Love (DJ Weirdo & Sim Remix)"),
        ("Stingray & Sonic Driver", "Cold As Ice (El Bruto Remix)"),
        ("Highlander", "Hold Me Now (Bass-D & King Matthew Remix)"),
        ("Juggernaut", 'Ruffneck Rules Da Artcore Scene (12" Edit)'),
        ("Diss Reaction", "Jiiieehaaaa "),
        ("Flamman And Abraxas", "Good To Go (Radio Mix)"),
        ("Critical Mass", "Dancing Together"),
        (
            "Charly Lownoise & Mental Theo",
            "Ultimate Sex Track (Bass-D & King Matthew Remix)",
        ),
    ]

    def __init__(self, zone_id, name, entry_id, coordinator, device_class=None):
        """Initialize the demo device."""
        self._name = name
        self._player_state = STATE_PLAYING
        self._volume_muted = False
        self._shuffle = False
        self._sound_mode_list = SOUND_MODE_LIST
        self._sound_mode = DEFAULT_SOUND_MODE
        self._device_class = device_class
        self._zone_id = zone_id
        self.coordinator: MusicCastDataUpdateCoordinator = coordinator

        self._volume_min = self.coordinator.data.zones[self._zone_id].min_volume
        self._volume_max = self.coordinator.data.zones[self._zone_id].max_volume

        self._cur_track = 0
        self._repeat = REPEAT_MODE_OFF

        super().__init__(
            entry_id=entry_id,
            coordinator=coordinator,
            name=name,
            icon="mdi:speaker",
        )

    async def async_added_to_hass(self):
        """Run when this Entity has been added to HA."""
        # Sensors should also register callbacks to HA when their state changes
        self.coordinator.musiccast.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        """Entity being removed from hass."""
        # The opposite of async_added_to_hass. Remove any registered call backs here.
        self.coordinator.musiccast.remove_callback(self.async_write_ha_state)

    @property
    def should_poll(self):
        """Push an update after each command."""
        return False

    @property
    def name(self):
        """Return the name of the media player."""
        return self._name

    @property
    def state(self):
        """Return the state of the player."""
        return (
            STATE_PLAYING
            if self.coordinator.data.zones[self._zone_id].power == "on"
            else STATE_OFF
        )

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
        return self._shuffle

    @property
    def sound_mode(self):
        """Return the current sound mode."""
        return self._sound_mode

    @property
    def sound_mode_list(self):
        """Return a list of available sound modes."""
        return self._sound_mode_list

    @property
    def device_class(self):
        """Return the device class of the media player."""
        return self._device_class

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this media_player."""
        macs = self.coordinator.data.mac_addresses
        return f"{macs}_{self._zone_id}"

    async def async_turn_on(self):
        """Turn the media player on."""
        await self.coordinator.musiccast.device.request(
            Zone.set_power(self._zone_id, "on")
        )
        self.schedule_update_ha_state()

    async def async_turn_off(self):
        """Turn the media player off."""
        await self.coordinator.musiccast.device.request(
            Zone.set_power(self._zone_id, "standby")
        )
        self.schedule_update_ha_state()

    async def async_mute_volume(self, mute):
        """Mute the volume."""

        await self.coordinator.musiccast.device.request(
            Zone.set_mute(self._zone_id, mute)
        )

        self.schedule_update_ha_state()

    async def async_set_volume_level(self, volume):
        """Set the volume level, range 0..1."""
        vol = self._volume_min + (self._volume_max - self._volume_min) * volume

        await self.coordinator.musiccast.device.request(
            Zone.set_volume(self._zone_id, round(vol), 1)
        )

        self.schedule_update_ha_state()

    def media_play(self):
        """Send play command."""
        self._player_state = STATE_PLAYING
        self.schedule_update_ha_state()

    def media_pause(self):
        """Send pause command."""
        self._player_state = STATE_PAUSED
        self.schedule_update_ha_state()

    def set_shuffle(self, shuffle):
        """Enable/disable shuffle mode."""
        self._shuffle = shuffle
        self.schedule_update_ha_state()

    def select_sound_mode(self, sound_mode):
        """Select sound mode."""
        self._sound_mode = sound_mode
        self.schedule_update_ha_state()

    @property
    def media_content_id(self):
        """Return the content ID of current playing media."""
        return "bounzz-1"

    @property
    def media_content_type(self):
        """Return the content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def media_duration(self):
        """Return the duration of current playing media in seconds."""
        return 213

    @property
    def media_image_url(self):
        """Return the image url of current playing media."""
        return "https://graph.facebook.com/v2.5/107771475912710/picture?type=large"

    @property
    def media_title(self):
        """Return the title of current playing media."""
        return self.tracks[self._cur_track][1] if self.tracks else ""

    @property
    def media_artist(self):
        """Return the artist of current playing media (Music track only)."""
        return self.tracks[self._cur_track][0] if self.tracks else ""

    @property
    def media_album_name(self):
        """Return the album of current playing media (Music track only)."""
        return "Bounzz"

    @property
    def media_track(self):
        """Return the track number of current media (Music track only)."""
        return self._cur_track + 1

    @property
    def repeat(self):
        """Return current repeat mode."""
        return self._repeat

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return MUSIC_PLAYER_SUPPORT

    def media_previous_track(self):
        """Send previous track command."""
        if self._cur_track > 0:
            self._cur_track -= 1
            self.schedule_update_ha_state()

    def media_next_track(self):
        """Send next track command."""
        if self._cur_track < len(self.tracks) - 1:
            self._cur_track += 1
            self.schedule_update_ha_state()

    def clear_playlist(self):
        """Clear players playlist."""
        self.tracks = []
        self._cur_track = 0
        self._player_state = STATE_OFF
        self.schedule_update_ha_state()

    def set_repeat(self, repeat):
        """Enable/disable repeat mode."""
        self._repeat = repeat
        self.schedule_update_ha_state()
