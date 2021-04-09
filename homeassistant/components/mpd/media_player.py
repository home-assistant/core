"""Support to interact with a Music Player Daemon."""
from contextlib import suppress
from datetime import timedelta
import hashlib
import logging
import os

import mpd
from mpd.asyncio import MPDClient
import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MUSIC,
    MEDIA_TYPE_PLAYLIST,
    REPEAT_MODE_ALL,
    REPEAT_MODE_OFF,
    REPEAT_MODE_ONE,
    SUPPORT_CLEAR_PLAYLIST,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_REPEAT_SET,
    SUPPORT_SEEK,
    SUPPORT_SELECT_SOURCE,
    SUPPORT_SHUFFLE_SET,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle
import homeassistant.util.dt as dt_util

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "MPD"
DEFAULT_PORT = 6600

PLAYLIST_UPDATE_INTERVAL = timedelta(seconds=120)

SUPPORT_MPD = (
    SUPPORT_PAUSE
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_PLAY
    | SUPPORT_CLEAR_PLAYLIST
    | SUPPORT_REPEAT_SET
    | SUPPORT_SHUFFLE_SET
    | SUPPORT_SEEK
    | SUPPORT_STOP
    | SUPPORT_TURN_OFF
    | SUPPORT_TURN_ON
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the MPD platform."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    name = config.get(CONF_NAME)
    password = config.get(CONF_PASSWORD)

    entity = MpdDevice(host, port, password, name)
    async_add_entities([entity], True)


class MpdDevice(MediaPlayerEntity):
    """Representation of a MPD server."""

    # pylint: disable=no-member
    def __init__(self, server, port, password, name):
        """Initialize the MPD device."""
        self.server = server
        self.port = port
        self._name = name
        self.password = password

        self._status = None
        self._currentsong = None
        self._playlists = None
        self._currentplaylist = None
        self._is_connected = False
        self._muted = False
        self._muted_volume = None
        self._media_position_updated_at = None
        self._media_position = None
        self._commands = None

        # set up MPD client
        self._client = MPDClient()
        self._client.timeout = 30
        self._client.idletimeout = None

    async def _connect(self):
        """Connect to MPD."""
        try:
            await self._client.connect(self.server, self.port)

            if self.password is not None:
                await self._client.password(self.password)
        except mpd.ConnectionError:
            return

        self._is_connected = True

    def _disconnect(self):
        """Disconnect from MPD."""
        with suppress(mpd.ConnectionError):
            self._client.disconnect()
        self._is_connected = False
        self._status = None

    async def _fetch_status(self):
        """Fetch status from MPD."""
        self._status = await self._client.status()
        self._currentsong = await self._client.currentsong()

        position = self._status.get("elapsed")

        if position is None:
            position = self._status.get("time")

            if isinstance(position, str) and ":" in position:
                position = position.split(":")[0]

        if position is not None and self._media_position != position:
            self._media_position_updated_at = dt_util.utcnow()
            self._media_position = int(float(position))

        await self._update_playlists()

    @property
    def available(self):
        """Return true if MPD is available and connected."""
        return self._is_connected

    async def async_update(self):
        """Get the latest data and update the state."""
        try:
            if not self._is_connected:
                await self._connect()
                self._commands = list(await self._client.commands())

            await self._fetch_status()
        except (mpd.ConnectionError, OSError, BrokenPipeError, ValueError) as error:
            # Cleanly disconnect in case connection is not in valid state
            _LOGGER.debug("Error updating status: %s", error)
            self._disconnect()

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the media state."""
        if self._status is None:
            return STATE_OFF
        if self._status["state"] == "play":
            return STATE_PLAYING
        if self._status["state"] == "pause":
            return STATE_PAUSED
        if self._status["state"] == "stop":
            return STATE_OFF

        return STATE_OFF

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def media_content_id(self):
        """Return the content ID of current playing media."""
        return self._currentsong.get("file")

    @property
    def media_content_type(self):
        """Return the content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def media_duration(self):
        """Return the duration of current playing media in seconds."""
        # Time does not exist for streams
        return self._currentsong.get("time")

    @property
    def media_position(self):
        """Position of current playing media in seconds.

        This is returned as part of the mpd status rather than in the details
        of the current song.
        """
        return self._media_position

    @property
    def media_position_updated_at(self):
        """Last valid time of media position."""
        return self._media_position_updated_at

    @property
    def media_title(self):
        """Return the title of current playing media."""
        name = self._currentsong.get("name", None)
        title = self._currentsong.get("title", None)
        file_name = self._currentsong.get("file", None)

        if name is None and title is None:
            if file_name is None:
                return "None"
            return os.path.basename(file_name)
        if name is None:
            return title
        if title is None:
            return name

        return f"{name}: {title}"

    @property
    def media_artist(self):
        """Return the artist of current playing media (Music track only)."""
        return self._currentsong.get("artist")

    @property
    def media_album_name(self):
        """Return the album of current playing media (Music track only)."""
        return self._currentsong.get("album")

    @property
    def media_image_hash(self):
        """Hash value for media image."""
        file = self._currentsong.get("file")
        if file:
            return hashlib.sha256(file.encode("utf-8")).hexdigest()[:16]

        return None

    async def async_get_media_image(self):
        """Fetch media image of current playing track."""
        file = self._currentsong.get("file")
        if not file:
            return None, None

        # not all MPD implementations and versions support the `albumart` and `fetchpicture` commands
        can_albumart = "albumart" in self._commands
        can_readpicture = "readpicture" in self._commands

        response = None

        # read artwork embedded into the media file
        if can_readpicture:
            try:
                response = await self._client.readpicture(file)
            except mpd.CommandError as error:
                if error.errno is not mpd.FailureResponseCode.NO_EXIST:
                    _LOGGER.warning(
                        "Retrieving artwork through `readpicture` command failed: %s",
                        error,
                    )

        # read artwork contained in the media directory (cover.{jpg,png,tiff,bmp}) if none is embedded
        if can_albumart and not response:
            try:
                response = await self._client.albumart(file)
            except mpd.CommandError as error:
                if error.errno is not mpd.FailureResponseCode.NO_EXIST:
                    _LOGGER.warning(
                        "Retrieving artwork through `albumart` command failed: %s",
                        error,
                    )

        if not response:
            return None, None

        image = bytes(response.get("binary"))
        mime = response.get(
            "type", "image/png"
        )  # readpicture has type, albumart does not
        return (image, mime)

    @property
    def volume_level(self):
        """Return the volume level."""
        if "volume" in self._status:
            return int(self._status["volume"]) / 100
        return None

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        if self._status is None:
            return 0

        supported = SUPPORT_MPD
        if "volume" in self._status:
            supported |= SUPPORT_VOLUME_SET | SUPPORT_VOLUME_STEP | SUPPORT_VOLUME_MUTE
        if self._playlists is not None:
            supported |= SUPPORT_SELECT_SOURCE

        return supported

    @property
    def source(self):
        """Name of the current input source."""
        return self._currentplaylist

    @property
    def source_list(self):
        """Return the list of available input sources."""
        return self._playlists

    async def async_select_source(self, source):
        """Choose a different available playlist and play it."""
        await self.async_play_media(MEDIA_TYPE_PLAYLIST, source)

    @Throttle(PLAYLIST_UPDATE_INTERVAL)
    async def _update_playlists(self, **kwargs):
        """Update available MPD playlists."""
        try:
            self._playlists = []
            for playlist_data in await self._client.listplaylists():
                self._playlists.append(playlist_data["playlist"])
        except mpd.CommandError as error:
            self._playlists = None
            _LOGGER.warning("Playlists could not be updated: %s:", error)

    async def async_set_volume_level(self, volume):
        """Set volume of media player."""
        if "volume" in self._status:
            await self._client.setvol(int(volume * 100))

    async def async_volume_up(self):
        """Service to send the MPD the command for volume up."""
        if "volume" in self._status:
            current_volume = int(self._status["volume"])

            if current_volume <= 100:
                self._client.setvol(current_volume + 5)

    async def async_volume_down(self):
        """Service to send the MPD the command for volume down."""
        if "volume" in self._status:
            current_volume = int(self._status["volume"])

            if current_volume >= 0:
                await self._client.setvol(current_volume - 5)

    async def async_media_play(self):
        """Service to send the MPD the command for play/pause."""
        if self._status["state"] == "pause":
            await self._client.pause(0)
        else:
            await self._client.play()

    async def async_media_pause(self):
        """Service to send the MPD the command for play/pause."""
        await self._client.pause(1)

    async def async_media_stop(self):
        """Service to send the MPD the command for stop."""
        await self._client.stop()

    async def async_media_next_track(self):
        """Service to send the MPD the command for next track."""
        await self._client.next()

    async def async_media_previous_track(self):
        """Service to send the MPD the command for previous track."""
        await self._client.previous()

    async def async_mute_volume(self, mute):
        """Mute. Emulated with set_volume_level."""
        if "volume" in self._status:
            if mute:
                self._muted_volume = self.volume_level
                await self.async_set_volume_level(0)
            elif self._muted_volume is not None:
                await self.async_set_volume_level(self._muted_volume)
            self._muted = mute

    async def async_play_media(self, media_type, media_id, **kwargs):
        """Send the media player the command for playing a playlist."""
        _LOGGER.debug("Playing playlist: %s", media_id)
        if media_type == MEDIA_TYPE_PLAYLIST:
            if media_id in self._playlists:
                self._currentplaylist = media_id
            else:
                self._currentplaylist = None
                _LOGGER.warning("Unknown playlist name %s", media_id)
            await self._client.clear()
            await self._client.load(media_id)
            await self._client.play()
        else:
            await self._client.clear()
            self._currentplaylist = None
            await self._client.add(media_id)
            await self._client.play()

    @property
    def repeat(self):
        """Return current repeat mode."""
        if self._status["repeat"] == "1":
            if self._status["single"] == "1":
                return REPEAT_MODE_ONE
            return REPEAT_MODE_ALL
        return REPEAT_MODE_OFF

    async def async_set_repeat(self, repeat):
        """Set repeat mode."""
        if repeat == REPEAT_MODE_OFF:
            await self._client.repeat(0)
            await self._client.single(0)
        else:
            await self._client.repeat(1)
            if repeat == REPEAT_MODE_ONE:
                await self._client.single(1)
            else:
                await self._client.single(0)

    @property
    def shuffle(self):
        """Boolean if shuffle is enabled."""
        return bool(int(self._status["random"]))

    async def async_set_shuffle(self, shuffle):
        """Enable/disable shuffle mode."""
        await self._client.random(int(shuffle))

    async def async_turn_off(self):
        """Service to send the MPD the command to stop playing."""
        await self._client.stop()

    async def async_turn_on(self):
        """Service to send the MPD the command to start playing."""
        await self._client.play()
        await self._update_playlists(no_throttle=True)

    async def async_clear_playlist(self):
        """Clear players playlist."""
        await self._client.clear()

    async def async_media_seek(self, position):
        """Send seek command."""
        await self._client.seekcur(position)
