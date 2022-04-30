"""Demo implementation of the media player."""
from __future__ import annotations

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
)
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MOVIE,
    MEDIA_TYPE_MUSIC,
    MEDIA_TYPE_TVSHOW,
    REPEAT_MODE_OFF,
    MediaPlayerEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_OFF, STATE_PAUSED, STATE_PLAYING
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the media player demo platform."""
    async_add_entities(
        [
            DemoYoutubePlayer(
                "Living Room",
                "eyU3bRy2x44",
                "♥♥ The Best Fireplace Video (3 hours)",
                300,
            ),
            DemoYoutubePlayer(
                "Bedroom", "kxopViU98Xo", "Epic sax guy 10 hours", 360000
            ),
            DemoMusicPlayer(),
            DemoMusicPlayer("Kitchen"),
            DemoTVShowPlayer(),
        ]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Demo config entry."""
    await async_setup_platform(hass, {}, async_add_entities)


SOUND_MODE_LIST = ["Music", "Movie"]
DEFAULT_SOUND_MODE = "Music"

YOUTUBE_PLAYER_SUPPORT = (
    MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.PLAY_MEDIA
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.SHUFFLE_SET
    | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    | MediaPlayerEntityFeature.SEEK
    | MediaPlayerEntityFeature.STOP
)

MUSIC_PLAYER_SUPPORT = (
    MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.CLEAR_PLAYLIST
    | MediaPlayerEntityFeature.GROUPING
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.SHUFFLE_SET
    | MediaPlayerEntityFeature.REPEAT_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    | MediaPlayerEntityFeature.STOP
)

NETFLIX_PLAYER_SUPPORT = (
    MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.SHUFFLE_SET
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    | MediaPlayerEntityFeature.STOP
)


class AbstractDemoPlayer(MediaPlayerEntity):
    """A demo media players."""

    # We only implement the methods that we support

    def __init__(self, name, device_class=None):
        """Initialize the demo device."""
        self._name = name
        self._player_state = STATE_PLAYING
        self._volume_level = 1.0
        self._volume_muted = False
        self._shuffle = False
        self._sound_mode_list = SOUND_MODE_LIST
        self._sound_mode = DEFAULT_SOUND_MODE
        self._device_class = device_class

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
        return self._player_state

    @property
    def volume_level(self):
        """Return the volume level of the media player (0..1)."""
        return self._volume_level

    @property
    def is_volume_muted(self):
        """Return boolean if volume is currently muted."""
        return self._volume_muted

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

    def turn_on(self):
        """Turn the media player on."""
        self._player_state = STATE_PLAYING
        self.schedule_update_ha_state()

    def turn_off(self):
        """Turn the media player off."""
        self._player_state = STATE_OFF
        self.schedule_update_ha_state()

    def mute_volume(self, mute):
        """Mute the volume."""
        self._volume_muted = mute
        self.schedule_update_ha_state()

    def volume_up(self):
        """Increase volume."""
        self._volume_level = min(1.0, self._volume_level + 0.1)
        self.schedule_update_ha_state()

    def volume_down(self):
        """Decrease volume."""
        self._volume_level = max(0.0, self._volume_level - 0.1)
        self.schedule_update_ha_state()

    def set_volume_level(self, volume):
        """Set the volume level, range 0..1."""
        self._volume_level = volume
        self.schedule_update_ha_state()

    def media_play(self):
        """Send play command."""
        self._player_state = STATE_PLAYING
        self.schedule_update_ha_state()

    def media_pause(self):
        """Send pause command."""
        self._player_state = STATE_PAUSED
        self.schedule_update_ha_state()

    def media_stop(self):
        """Send stop command."""
        self._player_state = STATE_OFF
        self.schedule_update_ha_state()

    def set_shuffle(self, shuffle):
        """Enable/disable shuffle mode."""
        self._shuffle = shuffle
        self.schedule_update_ha_state()

    def select_sound_mode(self, sound_mode):
        """Select sound mode."""
        self._sound_mode = sound_mode
        self.schedule_update_ha_state()


class DemoYoutubePlayer(AbstractDemoPlayer):
    """A Demo media player that only supports YouTube."""

    # We only implement the methods that we support

    def __init__(self, name, youtube_id=None, media_title=None, duration=360):
        """Initialize the demo device."""
        super().__init__(name)
        self.youtube_id = youtube_id
        self._media_title = media_title
        self._duration = duration
        self._progress = int(duration * 0.15)
        self._progress_updated_at = dt_util.utcnow()

    @property
    def media_content_id(self):
        """Return the content ID of current playing media."""
        return self.youtube_id

    @property
    def media_content_type(self):
        """Return the content type of current playing media."""
        return MEDIA_TYPE_MOVIE

    @property
    def media_duration(self):
        """Return the duration of current playing media in seconds."""
        return self._duration

    @property
    def media_image_url(self):
        """Return the image url of current playing media."""
        return f"https://img.youtube.com/vi/{self.youtube_id}/hqdefault.jpg"

    @property
    def media_title(self):
        """Return the title of current playing media."""
        return self._media_title

    @property
    def app_name(self):
        """Return the current running application."""
        return "YouTube"

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return YOUTUBE_PLAYER_SUPPORT

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        if self._progress is None:
            return None

        position = self._progress

        if self._player_state == STATE_PLAYING:
            position += (dt_util.utcnow() - self._progress_updated_at).total_seconds()

        return position

    @property
    def media_position_updated_at(self):
        """When was the position of the current playing media valid.

        Returns value from homeassistant.util.dt.utcnow().
        """
        if self._player_state == STATE_PLAYING:
            return self._progress_updated_at

    def play_media(self, media_type, media_id, **kwargs):
        """Play a piece of media."""
        self.youtube_id = media_id
        self.schedule_update_ha_state()

    def media_pause(self):
        """Send pause command."""
        self._progress = self.media_position
        self._progress_updated_at = dt_util.utcnow()
        super().media_pause()


class DemoMusicPlayer(AbstractDemoPlayer):
    """A Demo media player."""

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

    def __init__(self, name="Walkman"):
        """Initialize the demo device."""
        super().__init__(name)
        self._cur_track = 0
        self._group_members = []
        self._repeat = REPEAT_MODE_OFF

    @property
    def group_members(self):
        """List of players which are currently grouped together."""
        return self._group_members

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

    def join_players(self, group_members):
        """Join `group_members` as a player group with the current player."""
        self._group_members = [
            self.entity_id,
        ] + group_members
        self.schedule_update_ha_state()

    def unjoin_player(self):
        """Remove this player from any group."""
        self._group_members = []
        self.schedule_update_ha_state()


class DemoTVShowPlayer(AbstractDemoPlayer):
    """A Demo media player that only supports YouTube."""

    # We only implement the methods that we support

    _attr_device_class = MediaPlayerDeviceClass.TV

    def __init__(self):
        """Initialize the demo device."""
        super().__init__("Lounge room")
        self._cur_episode = 1
        self._episode_count = 13
        self._source = "dvd"
        self._source_list = ["dvd", "youtube"]

    @property
    def media_content_id(self):
        """Return the content ID of current playing media."""
        return "house-of-cards-1"

    @property
    def media_content_type(self):
        """Return the content type of current playing media."""
        return MEDIA_TYPE_TVSHOW

    @property
    def media_duration(self):
        """Return the duration of current playing media in seconds."""
        return 3600

    @property
    def media_image_url(self):
        """Return the image url of current playing media."""
        return "https://graph.facebook.com/v2.5/HouseofCards/picture?width=400"

    @property
    def media_title(self):
        """Return the title of current playing media."""
        return f"Chapter {self._cur_episode}"

    @property
    def media_series_title(self):
        """Return the series title of current playing media (TV Show only)."""
        return "House of Cards"

    @property
    def media_season(self):
        """Return the season of current playing media (TV Show only)."""
        return 1

    @property
    def media_episode(self):
        """Return the episode of current playing media (TV Show only)."""
        return self._cur_episode

    @property
    def app_name(self):
        """Return the current running application."""
        return "Netflix"

    @property
    def source(self):
        """Return the current input source."""
        return self._source

    @property
    def source_list(self):
        """List of available sources."""
        return self._source_list

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return NETFLIX_PLAYER_SUPPORT

    def media_previous_track(self):
        """Send previous track command."""
        if self._cur_episode > 1:
            self._cur_episode -= 1
            self.schedule_update_ha_state()

    def media_next_track(self):
        """Send next track command."""
        if self._cur_episode < self._episode_count:
            self._cur_episode += 1
            self.schedule_update_ha_state()

    def select_source(self, source):
        """Set the input source."""
        self._source = source
        self.schedule_update_ha_state()
