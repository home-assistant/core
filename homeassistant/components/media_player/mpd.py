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

from homeassistant.components.media_player import (
    MediaPlayerDevice, STATE_NO_APP, ATTR_MEDIA_STATE,
    ATTR_MEDIA_CONTENT_ID, ATTR_MEDIA_TITLE, ATTR_MEDIA_ARTIST,
    ATTR_MEDIA_ALBUM, ATTR_MEDIA_DATE, ATTR_MEDIA_DURATION,
    ATTR_MEDIA_VOLUME, MEDIA_STATE_PAUSED, MEDIA_STATE_PLAYING,
    MEDIA_STATE_STOPPED, MEDIA_STATE_UNKNOWN)

_LOGGER = logging.getLogger(__name__)


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

    def __init__(self, server, port, location):
        from mpd import MPDClient

        self.server = server
        self.port = port
        self._name = location
        self.state_attr = {ATTR_MEDIA_STATE: MEDIA_STATE_STOPPED}

        self.client = MPDClient()
        self.client.timeout = 10
        self.client.idletimeout = None
        self.client.connect(self.server, self.port)

    @property
    def name(self):
        """ Returns the name of the device. """
        return self._name

    # pylint: disable=no-member
    @property
    def state(self):
        """ Returns the state of the device. """
        status = self.client.status()

        if status is None:
            return STATE_NO_APP
        else:
            return self.client.currentsong()['artist']

    @property
    def media_state(self):
        """ Returns the media state. """
        media_controller = self.client.status()

        if media_controller['state'] == 'play':
            return MEDIA_STATE_PLAYING
        elif media_controller['state'] == 'pause':
            return MEDIA_STATE_PAUSED
        elif media_controller['state'] == 'stop':
            return MEDIA_STATE_STOPPED
        else:
            return MEDIA_STATE_UNKNOWN

    # pylint: disable=no-member
    @property
    def state_attributes(self):
        """ Returns the state attributes. """
        status = self.client.status()
        current_song = self.client.currentsong()

        if not status and not current_song:
            state_attr = {}

            if current_song['id']:
                state_attr[ATTR_MEDIA_CONTENT_ID] = current_song['id']

            if current_song['date']:
                state_attr[ATTR_MEDIA_DATE] = current_song['date']

            if current_song['title']:
                state_attr[ATTR_MEDIA_TITLE] = current_song['title']

            if current_song['time']:
                state_attr[ATTR_MEDIA_DURATION] = current_song['time']

            if current_song['artist']:
                state_attr[ATTR_MEDIA_ARTIST] = current_song['artist']

            if current_song['album']:
                state_attr[ATTR_MEDIA_ALBUM] = current_song['album']

            state_attr[ATTR_MEDIA_VOLUME] = status['volume']

            return state_attr

    def turn_off(self):
        """ Service to exit the running MPD. """
        self.client.stop()

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

    def media_play_pause(self):
        """ Service to send the MPD the command for play/pause. """
        self.client.pause()

    def media_play(self):
        """ Service to send the MPD the command for play/pause. """
        self.client.start()

    def media_pause(self):
        """ Service to send the MPD the command for play/pause. """
        self.client.pause()

    def media_next_track(self):
        """ Service to send the MPD the command for next track. """
        self.client.next()

    def media_prev_track(self):
        """ Service to send the MPD the command for previous track. """
        self.client.previous()
