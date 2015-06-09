"""
homeassistant.components.media_player.mpd
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides functionality to interact with a Music Player Daemon.

Configuration:

To use MPD you will need to add something like the following to your
config/configuration.yaml

media_player:
  platform: mpd
  server: 127.0.0.1
  port: 6600
  location: bedroom

Variables:

server
*Required
IP address of the Music Player Daemon. Example: 192.168.1.32

port
*Optional
Port of the Music Player Daemon, defaults to 6600. Example: 6600

location
*Optional
Location of your Music Player Daemon.
"""
import logging
import socket

from homeassistant.const import (
    STATE_PLAYING, STATE_PAUSED, STATE_OFF)

from homeassistant.components.media_player import (
    MediaPlayerDevice,
    SUPPORT_PAUSE, SUPPORT_VOLUME_SET, SUPPORT_TURN_OFF,
    SUPPORT_PREVIOUS_TRACK, SUPPORT_NEXT_TRACK,
    MEDIA_TYPE_MUSIC)

_LOGGER = logging.getLogger(__name__)


SUPPORT_MPD = SUPPORT_PAUSE | SUPPORT_VOLUME_SET | SUPPORT_TURN_OFF | \
    SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the MPD platform. """

    daemon = config.get('server', None)
    port = config.get('port', 6600)
    location = config.get('location', 'MPD')

    try:
        from mpd import MPDClient

    except ImportError:
        _LOGGER.exception(
            "Unable to import mpd2. "
            "Did you maybe not install the 'python-mpd2' package?")

        return False

    # pylint: disable=no-member
    try:
        mpd_client = MPDClient()
        mpd_client.connect(daemon, port)
        mpd_client.close()
        mpd_client.disconnect()
    except socket.error:
        _LOGGER.error(
            "Unable to connect to MPD. "
            "Please check your settings")

        return False

    mpd = []
    mpd.append(MpdDevice(daemon, port, location))
    add_devices(mpd)


class MpdDevice(MediaPlayerDevice):
    """ Represents a MPD server. """

    # MPD confuses pylint
    # pylint: disable=no-member, abstract-method

    def __init__(self, server, port, location):
        from mpd import MPDClient

        self.server = server
        self.port = port
        self._name = location

        self.client = MPDClient()
        self.client.timeout = 10
        self.client.idletimeout = None
        self.client.connect(self.server, self.port)

    @property
    def name(self):
        """ Returns the name of the device. """
        return self._name

    @property
    def state(self):
        """ Returns the media state. """
        status = self.client.status()

        if status['state'] == 'play':
            return STATE_PLAYING
        elif status['state'] == 'pause':
            return STATE_PAUSED
        else:
            return STATE_OFF

    @property
    def media_content_id(self):
        """ Content ID of current playing media. """
        current_song = self.client.currentsong()
        return current_song['id']

    @property
    def media_content_type(self):
        """ Content type of current playing media. """
        return MEDIA_TYPE_MUSIC

    @property
    def media_duration(self):
        """ Duration of current playing media in seconds. """
        current_song = self.client.currentsong()
        return current_song['time']

    @property
    def media_title(self):
        """ Title of current playing media. """
        current_song = self.client.currentsong()
        return current_song['title']

    @property
    def media_artist(self):
        """ Artist of current playing media. (Music track only) """
        current_song = self.client.currentsong()
        return current_song['artist']

    @property
    def media_album_name(self):
        """ Album of current playing media. (Music track only) """
        current_song = self.client.currentsong()
        return current_song['album']

    @property
    def volume_level(self):
        status = self.client.status()
        return int(status['volume'])/100

    def turn_off(self):
        """ Service to exit the running MPD. """
        self.client.stop()

    def set_volume_level(self, volume):
        """ Sets volume """
        self.client.setvol(int(volume * 100))

    def volume_up(self):
        """ Service to send the MPD the command for volume up. """
        current_volume = self.client.status()['volume']

        if int(current_volume) <= 100:
            self.client.setvol(int(current_volume) + 5)

    def volume_down(self):
        """ Service to send the MPD the command for volume down. """
        current_volume = self.client.status()['volume']

        if int(current_volume) >= 0:
            self.client.setvol(int(current_volume) - 5)

    def media_play(self):
        """ Service to send the MPD the command for play/pause. """
        self.client.start()

    def media_pause(self):
        """ Service to send the MPD the command for play/pause. """
        self.client.pause()

    def media_next_track(self):
        """ Service to send the MPD the command for next track. """
        self.client.next()

    def media_previous_track(self):
        """ Service to send the MPD the command for previous track. """
        self.client.previous()
