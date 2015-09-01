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
  password: superSecretPassword123

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

password
*Optional
Password for your Music Player Daemon.
"""
import logging
import socket

try:
    import mpd
except ImportError:
    mpd = None


from homeassistant.const import (
    STATE_PLAYING, STATE_PAUSED, STATE_OFF)

from homeassistant.components.media_player import (
    MediaPlayerDevice,
    SUPPORT_PAUSE, SUPPORT_VOLUME_SET, SUPPORT_TURN_OFF,
    SUPPORT_PREVIOUS_TRACK, SUPPORT_NEXT_TRACK,
    MEDIA_TYPE_MUSIC)

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['python-mpd2==0.5.4']

SUPPORT_MPD = SUPPORT_PAUSE | SUPPORT_VOLUME_SET | SUPPORT_TURN_OFF | \
    SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the MPD platform. """

    daemon = config.get('server', None)
    port = config.get('port', 6600)
    location = config.get('location', 'MPD')
    password = config.get('password', None)

    global mpd  # pylint: disable=invalid-name
    if mpd is None:
        import mpd as mpd_
        mpd = mpd_

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
    """ Represents a MPD server. """

    # MPD confuses pylint
    # pylint: disable=no-member, abstract-method

    def __init__(self, server, port, location, password):
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
        try:
            self.status = self.client.status()
            self.currentsong = self.client.currentsong()
        except mpd.ConnectionError:
            self.client.connect(self.server, self.port)

            if self.password is not None:
                self.client.password(self.password)

            self.status = self.client.status()
            self.currentsong = self.client.currentsong()

    @property
    def name(self):
        """ Returns the name of the device. """
        return self._name

    @property
    def state(self):
        """ Returns the media state. """
        if self.status['state'] == 'play':
            return STATE_PLAYING
        elif self.status['state'] == 'pause':
            return STATE_PAUSED
        else:
            return STATE_OFF

    @property
    def media_content_id(self):
        """ Content ID of current playing media. """
        return self.currentsong['id']

    @property
    def media_content_type(self):
        """ Content type of current playing media. """
        return MEDIA_TYPE_MUSIC

    @property
    def media_duration(self):
        """ Duration of current playing media in seconds. """
        # Time does not exist for streams
        return self.currentsong.get('time')

    @property
    def media_title(self):
        """ Title of current playing media. """
        return self.currentsong['title']

    @property
    def media_artist(self):
        """ Artist of current playing media. (Music track only) """
        return self.currentsong.get('artist')

    @property
    def media_album_name(self):
        """ Album of current playing media. (Music track only) """
        return self.currentsong.get('album')

    @property
    def volume_level(self):
        return int(self.status['volume'])/100

    @property
    def supported_media_commands(self):
        """ Flags of media commands that are supported. """
        return SUPPORT_MPD

    def turn_off(self):
        """ Service to exit the running MPD. """
        self.client.stop()

    def set_volume_level(self, volume):
        """ Sets volume """
        self.client.setvol(int(volume * 100))

    def volume_up(self):
        """ Service to send the MPD the command for volume up. """
        current_volume = int(self.status['volume'])

        if current_volume <= 100:
            self.client.setvol(current_volume + 5)

    def volume_down(self):
        """ Service to send the MPD the command for volume down. """
        current_volume = int(self.status['volume'])

        if current_volume >= 0:
            self.client.setvol(current_volume - 5)

    def media_play(self):
        """ Service to send the MPD the command for play/pause. """
        self.client.pause(0)

    def media_pause(self):
        """ Service to send the MPD the command for play/pause. """
        self.client.pause(1)

    def media_next_track(self):
        """ Service to send the MPD the command for next track. """
        self.client.next()

    def media_previous_track(self):
        """ Service to send the MPD the command for previous track. """
        self.client.previous()
