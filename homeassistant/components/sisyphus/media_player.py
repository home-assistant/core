"""Support for track controls on the Sisyphus Kinetic Art Table."""
import logging

from homeassistant.components.media_player import MediaPlayerDevice
from homeassistant.components.media_player.const import (
    SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PLAY, SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SHUFFLE_SET, SUPPORT_TURN_OFF, SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, STATE_IDLE, STATE_OFF, STATE_PAUSED, STATE_PLAYING)

from . import DATA_SISYPHUS

_LOGGER = logging.getLogger(__name__)

MEDIA_TYPE_TRACK = 'sisyphus_track'

SUPPORTED_FEATURES = SUPPORT_VOLUME_MUTE \
    | SUPPORT_VOLUME_SET \
    | SUPPORT_TURN_OFF \
    | SUPPORT_TURN_ON \
    | SUPPORT_PAUSE \
    | SUPPORT_SHUFFLE_SET \
    | SUPPORT_PREVIOUS_TRACK \
    | SUPPORT_NEXT_TRACK \
    | SUPPORT_PLAY


# pylint: disable=unused-argument
def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up a media player entity for a Sisyphus table."""
    name = discovery_info[CONF_NAME]
    host = discovery_info[CONF_HOST]
    add_entities(
        [SisyphusPlayer(name, host, hass.data[DATA_SISYPHUS][name])], True)


class SisyphusPlayer(MediaPlayerDevice):
    """Representation of a Sisyphus table as a media player device."""

    def __init__(self, name, host, table):
        """Initialize the Sisyphus media device."""
        self._name = name
        self._host = host
        self._table = table

    async def async_added_to_hass(self):
        """Add listeners after this object has been initialized."""
        self._table.add_listener(
            lambda: self.async_schedule_update_ha_state(False))

    @property
    def name(self):
        """Return the name of the table."""
        return self._name

    @property
    def state(self):
        """Return the current state of the table; sleeping maps to off."""
        if self._table.state in ["homing", "playing"]:
            return STATE_PLAYING
        if self._table.state == "paused":
            if self._table.is_sleeping:
                return STATE_OFF

            return STATE_PAUSED
        if self._table.state == "waiting":
            return STATE_IDLE

        return None

    @property
    def volume_level(self):
        """Return the current playback speed (0..1)."""
        return self._table.speed

    @property
    def shuffle(self):
        """Return True if the current playlist is in shuffle mode."""
        return self._table.is_shuffle

    async def async_set_shuffle(self, shuffle):
        """Change the shuffle mode of the current playlist."""
        await self._table.set_shuffle(shuffle)

    @property
    def media_playlist(self):
        """Return the name of the current playlist."""
        return self._table.active_playlist.name \
            if self._table.active_playlist \
            else None

    @property
    def media_title(self):
        """Return the title of the current track."""
        return self._table.active_track.name \
            if self._table.active_track \
            else None

    @property
    def media_content_type(self):
        """Return the content type currently playing; i.e. a Sisyphus track."""
        return MEDIA_TYPE_TRACK

    @property
    def media_content_id(self):
        """Return the track ID of the current track."""
        return self._table.active_track.id \
            if self._table.active_track \
            else None

    @property
    def supported_features(self):
        """Return the features supported by this table."""
        return SUPPORTED_FEATURES

    @property
    def media_image_url(self):
        """Return the URL for a thumbnail image of the current track."""
        from sisyphus_control import Track
        if self._table.active_track:
            return self._table.active_track.get_thumbnail_url(
                Track.ThumbnailSize.LARGE)

        return super.media_image_url()

    async def async_turn_on(self):
        """Wake up a sleeping table."""
        await self._table.wakeup()

    async def async_turn_off(self):
        """Put the table to sleep."""
        await self._table.sleep()

    async def async_volume_down(self):
        """Slow down playback."""
        await self._table.set_speed(max(0, self._table.speed - 0.1))

    async def async_volume_up(self):
        """Speed up playback."""
        await self._table.set_speed(min(1.0, self._table.speed + 0.1))

    async def async_set_volume_level(self, volume):
        """Set playback speed (0..1)."""
        await self._table.set_speed(volume)

    async def async_media_play(self):
        """Start playing."""
        await self._table.play()

    async def async_media_pause(self):
        """Pause."""
        await self._table.pause()

    async def async_media_next_track(self):
        """Skip to next track."""
        cur_track_index = self._get_current_track_index()

        await self._table.active_playlist.play(
            self._table.active_playlist.tracks[cur_track_index + 1])

    async def async_media_previous_track(self):
        """Skip to previous track."""
        cur_track_index = self._get_current_track_index()

        await self._table.active_playlist.play(
            self._table.active_playlist.tracks[cur_track_index - 1])

    def _get_current_track_index(self):
        for index, track in enumerate(self._table.active_playlist.tracks):
            if track.id == self._table.active_track.id:
                return index

        return -1
