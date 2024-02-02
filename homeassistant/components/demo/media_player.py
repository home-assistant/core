"""Demo implementation of the media player."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.util.dt as dt_util


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Demo config entry."""
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
            DemoBrowsePlayer("Browse"),
            DemoGroupPlayer("Group"),
        ]
    )


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

BROWSE_PLAYER_SUPPORT = MediaPlayerEntityFeature.BROWSE_MEDIA


class AbstractDemoPlayer(MediaPlayerEntity):
    """A demo media players."""

    _attr_should_poll = False
    _attr_sound_mode_list = SOUND_MODE_LIST

    # We only implement the methods that we support

    def __init__(
        self, name: str, device_class: MediaPlayerDeviceClass | None = None
    ) -> None:
        """Initialize the demo device."""
        self._attr_name = name
        self._attr_state = MediaPlayerState.PLAYING
        self._attr_volume_level = 1.0
        self._attr_is_volume_muted = False
        self._attr_shuffle = False
        self._attr_sound_mode = DEFAULT_SOUND_MODE
        self._attr_device_class = device_class

    def turn_on(self) -> None:
        """Turn the media player on."""
        self._attr_state = MediaPlayerState.PLAYING
        self.schedule_update_ha_state()

    def turn_off(self) -> None:
        """Turn the media player off."""
        self._attr_state = MediaPlayerState.OFF
        self.schedule_update_ha_state()

    def mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        self._attr_is_volume_muted = mute
        self.schedule_update_ha_state()

    def volume_up(self) -> None:
        """Increase volume."""
        assert self.volume_level is not None
        self._attr_volume_level = min(1.0, self.volume_level + 0.1)
        self.schedule_update_ha_state()

    def volume_down(self) -> None:
        """Decrease volume."""
        assert self.volume_level is not None
        self._attr_volume_level = max(0.0, self.volume_level - 0.1)
        self.schedule_update_ha_state()

    def set_volume_level(self, volume: float) -> None:
        """Set the volume level, range 0..1."""
        self._attr_volume_level = volume
        self.schedule_update_ha_state()

    def media_play(self) -> None:
        """Send play command."""
        self._attr_state = MediaPlayerState.PLAYING
        self.schedule_update_ha_state()

    def media_pause(self) -> None:
        """Send pause command."""
        self._attr_state = MediaPlayerState.PAUSED
        self.schedule_update_ha_state()

    def media_stop(self) -> None:
        """Send stop command."""
        self._attr_state = MediaPlayerState.OFF
        self.schedule_update_ha_state()

    def set_shuffle(self, shuffle: bool) -> None:
        """Enable/disable shuffle mode."""
        self._attr_shuffle = shuffle
        self.schedule_update_ha_state()

    def select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode."""
        self._attr_sound_mode = sound_mode
        self.schedule_update_ha_state()


class DemoYoutubePlayer(AbstractDemoPlayer):
    """A Demo media player that only supports YouTube."""

    # We only implement the methods that we support

    _attr_app_name = "YouTube"
    _attr_media_content_type = MediaType.MOVIE
    _attr_supported_features = YOUTUBE_PLAYER_SUPPORT

    def __init__(
        self, name: str, youtube_id: str, media_title: str, duration: int
    ) -> None:
        """Initialize the demo device."""
        super().__init__(name)
        self._attr_media_content_id = youtube_id
        self._attr_media_title = media_title
        self._attr_media_duration = duration
        self._progress: int | None = int(duration * 0.15)
        self._progress_updated_at = dt_util.utcnow()

    @property
    def media_image_url(self) -> str:
        """Return the image url of current playing media."""
        return f"https://img.youtube.com/vi/{self.media_content_id}/hqdefault.jpg"

    @property
    def media_position(self) -> int | None:
        """Position of current playing media in seconds."""
        if self._progress is None:
            return None

        position = self._progress

        if self.state == MediaPlayerState.PLAYING:
            position += int(
                (dt_util.utcnow() - self._progress_updated_at).total_seconds()
            )

        return position

    @property
    def media_position_updated_at(self) -> datetime | None:
        """When was the position of the current playing media valid.

        Returns value from homeassistant.util.dt.utcnow().
        """
        if self.state == MediaPlayerState.PLAYING:
            return self._progress_updated_at
        return None

    def play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        self._attr_media_content_id = media_id
        self.schedule_update_ha_state()

    def media_pause(self) -> None:
        """Send pause command."""
        self._progress = self.media_position
        self._progress_updated_at = dt_util.utcnow()
        super().media_pause()


class DemoMusicPlayer(AbstractDemoPlayer):
    """A Demo media player."""

    # We only implement the methods that we support

    _attr_media_album_name = "Bounzz"
    _attr_media_content_id = "bounzz-1"
    _attr_media_content_type = MediaType.MUSIC
    _attr_media_duration = 213
    _attr_media_image_url = (
        "https://graph.facebook.com/v2.5/107771475912710/picture?type=large"
    )
    _attr_supported_features = MUSIC_PLAYER_SUPPORT

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

    def __init__(self, name: str = "Walkman") -> None:
        """Initialize the demo device."""
        super().__init__(name)
        self._cur_track = 0
        self._attr_group_members: list[str] = []
        self._attr_repeat = RepeatMode.OFF

    @property
    def media_title(self) -> str:
        """Return the title of current playing media."""
        return self.tracks[self._cur_track][1] if self.tracks else ""

    @property
    def media_artist(self) -> str:
        """Return the artist of current playing media (Music track only)."""
        return self.tracks[self._cur_track][0] if self.tracks else ""

    @property
    def media_track(self) -> int:
        """Return the track number of current media (Music track only)."""
        return self._cur_track + 1

    def media_previous_track(self) -> None:
        """Send previous track command."""
        if self._cur_track > 0:
            self._cur_track -= 1
            self.schedule_update_ha_state()

    def media_next_track(self) -> None:
        """Send next track command."""
        if self._cur_track < len(self.tracks) - 1:
            self._cur_track += 1
            self.schedule_update_ha_state()

    def clear_playlist(self) -> None:
        """Clear players playlist."""
        self.tracks = []
        self._cur_track = 0
        self._attr_state = MediaPlayerState.OFF
        self.schedule_update_ha_state()

    def set_repeat(self, repeat: RepeatMode) -> None:
        """Enable/disable repeat mode."""
        self._attr_repeat = repeat
        self.schedule_update_ha_state()

    def join_players(self, group_members: list[str]) -> None:
        """Join `group_members` as a player group with the current player."""
        self._attr_group_members = [
            self.entity_id,
        ] + group_members
        self.schedule_update_ha_state()

    def unjoin_player(self) -> None:
        """Remove this player from any group."""
        self._attr_group_members = []
        self.schedule_update_ha_state()


class DemoTVShowPlayer(AbstractDemoPlayer):
    """A Demo media player that only supports Netflix."""

    # We only implement the methods that we support

    _attr_app_name = "Netflix"
    _attr_media_content_id = "house-of-cards-1"
    _attr_media_content_type = MediaType.TVSHOW
    _attr_media_duration = 3600
    _attr_media_image_url = (
        "https://graph.facebook.com/v2.5/HouseofCards/picture?width=400"
    )
    _attr_media_season = "1"
    _attr_media_series_title = "House of Cards"
    _attr_source_list = ["dvd", "youtube"]
    _attr_supported_features = NETFLIX_PLAYER_SUPPORT

    def __init__(self) -> None:
        """Initialize the demo device."""
        super().__init__("Lounge room", MediaPlayerDeviceClass.TV)
        self._cur_episode = 1
        self._episode_count = 13
        self._attr_source = "dvd"

    @property
    def media_title(self) -> str:
        """Return the title of current playing media."""
        return f"Chapter {self._cur_episode}"

    @property
    def media_episode(self) -> str:
        """Return the episode of current playing media (TV Show only)."""
        return str(self._cur_episode)

    def media_previous_track(self) -> None:
        """Send previous track command."""
        if self._cur_episode > 1:
            self._cur_episode -= 1
            self.schedule_update_ha_state()

    def media_next_track(self) -> None:
        """Send next track command."""
        if self._cur_episode < self._episode_count:
            self._cur_episode += 1
            self.schedule_update_ha_state()

    def select_source(self, source: str) -> None:
        """Set the input source."""
        self._attr_source = source
        self.schedule_update_ha_state()


class DemoBrowsePlayer(AbstractDemoPlayer):
    """A Demo media player that supports browse."""

    _attr_supported_features = BROWSE_PLAYER_SUPPORT


class DemoGroupPlayer(AbstractDemoPlayer):
    """A Demo media player that supports grouping."""

    _attr_supported_features = (
        YOUTUBE_PLAYER_SUPPORT
        | MediaPlayerEntityFeature.GROUPING
        | MediaPlayerEntityFeature.TURN_OFF
    )
