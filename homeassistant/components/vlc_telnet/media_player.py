"""Provide functionality to interact with the vlc telnet interface."""
import logging

from python_telnet_vlc import ConnectionError as ConnErr, VLCTelnet
import voluptuous as vol

from homeassistant.components.media_player import PLATFORM_SCHEMA, MediaPlayerEntity
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MUSIC,
    SUPPORT_CLEAR_PLAYLIST,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SEEK,
    SUPPORT_SHUFFLE_SET,
    SUPPORT_STOP,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    STATE_IDLE,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = "vlc_telnet"

DEFAULT_NAME = "VLC-TELNET"
DEFAULT_PORT = 4212

SUPPORT_VLC = (
    SUPPORT_PAUSE
    | SUPPORT_SEEK
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_PLAY_MEDIA
    | SUPPORT_STOP
    | SUPPORT_CLEAR_PLAYLIST
    | SUPPORT_PLAY
    | SUPPORT_SHUFFLE_SET
)
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.positive_int,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the vlc platform."""
    add_entities(
        [
            VlcDevice(
                config.get(CONF_NAME),
                config.get(CONF_HOST),
                config.get(CONF_PORT),
                config.get(CONF_PASSWORD),
            )
        ],
        True,
    )


class VlcDevice(MediaPlayerEntity):
    """Representation of a vlc player."""

    def __init__(self, name, host, port, passwd):
        """Initialize the vlc device."""
        self._instance = None
        self._name = name
        self._volume = None
        self._muted = None
        self._state = STATE_UNAVAILABLE
        self._media_position_updated_at = None
        self._media_position = None
        self._media_duration = None
        self._host = host
        self._port = port
        self._password = passwd
        self._vlc = None
        self._available = False
        self._volume_bkp = 0
        self._media_artist = ""
        self._media_title = ""

    def update(self):
        """Get the latest details from the device."""
        if self._vlc is None:
            try:
                self._vlc = VLCTelnet(self._host, self._password, self._port)
                self._state = STATE_IDLE
                self._available = True
            except (ConnErr, EOFError):
                self._available = False
                self._vlc = None
        else:
            try:
                status = self._vlc.status()
                if status:
                    if "volume" in status:
                        self._volume = int(status["volume"]) / 500.0
                    else:
                        self._volume = None
                    if "state" in status:
                        state = status["state"]
                        if state == "playing":
                            self._state = STATE_PLAYING
                        elif state == "paused":
                            self._state = STATE_PAUSED
                        else:
                            self._state = STATE_IDLE
                    else:
                        self._state = STATE_IDLE

                self._media_duration = self._vlc.get_length()
                self._media_position = self._vlc.get_time()

                info = self._vlc.info()
                if info:
                    self._media_artist = info[0].get("artist")
                    self._media_title = info[0].get("title")

            except (ConnErr, EOFError):
                self._available = False
                self._vlc = None

        return True

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_VLC

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        return self._media_duration

    @property
    def media_position(self):
        """Position of current playing media in seconds."""
        return self._media_position

    @property
    def media_position_updated_at(self):
        """When was the position of the current playing media valid."""
        return self._media_position_updated_at

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._media_title

    @property
    def media_artist(self):
        """Artist of current playing media, music track only."""
        return self._media_artist

    def media_seek(self, position):
        """Seek the media to a specific location."""
        track_length = self._vlc.get_length() / 1000
        self._vlc.seek(position / track_length)

    def mute_volume(self, mute):
        """Mute the volume."""
        if mute:
            self._volume_bkp = self._volume
            self._volume = 0
            self._vlc.set_volume("0")
        else:
            self._vlc.set_volume(str(self._volume_bkp))
            self._volume = self._volume_bkp

        self._muted = mute

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self._vlc.set_volume(str(volume * 500))
        self._volume = volume

    def media_play(self):
        """Send play command."""
        self._vlc.play()
        self._state = STATE_PLAYING

    def media_pause(self):
        """Send pause command."""
        self._vlc.pause()
        self._state = STATE_PAUSED

    def media_stop(self):
        """Send stop command."""
        self._vlc.stop()
        self._state = STATE_IDLE

    def play_media(self, media_type, media_id, **kwargs):
        """Play media from a URL or file."""
        if media_type != MEDIA_TYPE_MUSIC:
            _LOGGER.error(
                "Invalid media type %s. Only %s is supported",
                media_type,
                MEDIA_TYPE_MUSIC,
            )
            return
        self._vlc.add(media_id)
        self._state = STATE_PLAYING

    def media_previous_track(self):
        """Send previous track command."""
        self._vlc.prev()

    def media_next_track(self):
        """Send next track command."""
        self._vlc.next()

    def clear_playlist(self):
        """Clear players playlist."""
        self._vlc.clear()

    def set_shuffle(self, shuffle):
        """Enable/disable shuffle mode."""
        self._vlc.random(shuffle)
