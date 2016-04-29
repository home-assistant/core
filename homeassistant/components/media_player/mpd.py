"""
Support to interact with a Music Player Daemon.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.mpd/
"""
import logging
import socket

from homeassistant.components.media_player import (
    MEDIA_TYPE_MUSIC, SUPPORT_NEXT_TRACK, SUPPORT_PAUSE,
    SUPPORT_PREVIOUS_TRACK, SUPPORT_TURN_OFF, SUPPORT_TURN_ON,
    SUPPORT_VOLUME_SET, SUPPORT_PLAY_MEDIA, MEDIA_TYPE_PLAYLIST,
    MediaPlayerDevice)
from homeassistant.const import STATE_OFF, STATE_PAUSED, STATE_PLAYING

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['python-mpd2==0.5.5']

SUPPORT_MPD = SUPPORT_PAUSE | SUPPORT_VOLUME_SET | SUPPORT_TURN_OFF | \
    SUPPORT_TURN_ON | SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK | \
    SUPPORT_PLAY_MEDIA


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the MPD platform."""
    daemon = config.get('server', None)
    port = config.get('port', 6600)
    location = config.get('location', 'MPD')
    password = config.get('password', None)

    import mpd

    # pylint: disable=no-member
    try:
        mpd_client = mpd.MPDClient()
        mpd_client.connect(daemon, port)

        if password is not None:
            mpd_client.password(password)

        mpd_client.close()
        mpd_client.disconnect()
    except socket.error:
        _LOGGER.error(
            "Unable to connect to MPD. "
            "Please check your settings")

        return False
    except mpd.CommandError as error:

        if "incorrect password" in str(error):
            _LOGGER.error(
                "MPD reported incorrect password. "
                "Please check your password.")

            return False
        else:
            raise

    add_devices([MpdDevice(daemon, port, location, password)])


class MpdDevice(MediaPlayerDevice):
    """Representation of a MPD server."""

    # MPD confuses pylint
    # pylint: disable=no-member, too-many-public-methods, abstract-method
    def __init__(self, server, port, location, password):
        """Initialize the MPD device."""
        import mpd

        self.server = server
        self.port = port
        self._name = location
        self.password = password
        self.status = None
        self.currentsong = None

        self.client = mpd.MPDClient()
        self.client.timeout = 10
        self.client.idletimeout = None
        self.update()

    def update(self):
        """Get the latest data and update the state."""
        import mpd
        try:
            self.status = self.client.status()
            self.currentsong = self.client.currentsong()
        except (mpd.ConnectionError, BrokenPipeError, ValueError):
            # Cleanly disconnect in case connection is not in valid state
            try:
                self.client.disconnect()
            except mpd.ConnectionError:
                pass

            self.client.connect(self.server, self.port)

            if self.password is not None:
                self.client.password(self.password)

            self.status = self.client.status()
            self.currentsong = self.client.currentsong()

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the media state."""
        if self.status['state'] == 'play':
            return STATE_PLAYING
        elif self.status['state'] == 'pause':
            return STATE_PAUSED
        else:
            return STATE_OFF

    @property
    def media_content_id(self):
        """Content ID of current playing media."""
        return self.currentsong['id']

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        # Time does not exist for streams
        return self.currentsong.get('time')

    @property
    def media_title(self):
        """Title of current playing media."""
        name = self.currentsong.get('name', None)
        title = self.currentsong.get('title', None)

        if name is None and title is None:
            return "None"
        elif name is None:
            return title
        elif title is None:
            return name
        else:
            return '{}: {}'.format(name, title)

    @property
    def media_artist(self):
        """Artist of current playing media (Music track only)."""
        return self.currentsong.get('artist')

    @property
    def media_album_name(self):
        """Album of current playing media (Music track only)."""
        return self.currentsong.get('album')

    @property
    def volume_level(self):
        """Return the volume level."""
        return int(self.status['volume'])/100

    @property
    def supported_media_commands(self):
        """Flag of media commands that are supported."""
        return SUPPORT_MPD

    def turn_off(self):
        """Service to send the MPD the command to stop playing."""
        self.client.stop()

    def turn_on(self):
        """Service to send the MPD the command to start playing."""
        self.client.play()

    def set_volume_level(self, volume):
        """Set volume of media player."""
        self.client.setvol(int(volume * 100))

    def volume_up(self):
        """Service to send the MPD the command for volume up."""
        current_volume = int(self.status['volume'])

        if current_volume <= 100:
            self.client.setvol(current_volume + 5)

    def volume_down(self):
        """Service to send the MPD the command for volume down."""
        current_volume = int(self.status['volume'])

        if current_volume >= 0:
            self.client.setvol(current_volume - 5)

    def media_play(self):
        """Service to send the MPD the command for play/pause."""
        self.client.pause(0)

    def media_pause(self):
        """Service to send the MPD the command for play/pause."""
        self.client.pause(1)

    def media_next_track(self):
        """Service to send the MPD the command for next track."""
        self.client.next()

    def media_previous_track(self):
        """Service to send the MPD the command for previous track."""
        self.client.previous()

    def play_media(self, media_type, media_id, **kwargs):
        """Send the media player the command for playing a playlist."""
        _LOGGER.info(str.format("Playing playlist: {0}", media_id))
        if media_type == MEDIA_TYPE_PLAYLIST:
            self.client.clear()
            self.client.load(media_id)
            self.client.play()
        else:
            _LOGGER.error(str.format("Invalid media type. Expected: {0}",
                                     MEDIA_TYPE_PLAYLIST))
