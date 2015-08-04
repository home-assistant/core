"""
homeassistant.components.media_player.squeezebox
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides an interface to the Logitech SqueezeBox API

Configuration:

To use SqueezeBox add something like this to your configuration:

media_player:
  platform: squeezebox
  name: SqueezeBox
  server: 192.168.1.21
  player: Player1
  port: 9090
  user: user
  password: password

Variables:

name
*Optional
The name of the device

server
*Required
The address of the Logitech Media Server

player
*Required
The unique name of the player

port
*Optional
Telnet port to Logitech Media Server, default 9090

user
*Optional
User, if password protection is enabled

password
*Optional
Password, if password protection is enabled
"""

import logging
import telnetlib
import urllib.parse

from homeassistant.components.media_player import (
    MediaPlayerDevice, SUPPORT_PAUSE, SUPPORT_SEEK, SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_MUTE, SUPPORT_PREVIOUS_TRACK, SUPPORT_NEXT_TRACK,
    MEDIA_TYPE_MUSIC)
from homeassistant.const import (
    STATE_IDLE, STATE_PLAYING, STATE_PAUSED, STATE_OFF, STATE_UNKNOWN)

_LOGGER = logging.getLogger(__name__)

SUPPORT_SQUEEZEBOX = SUPPORT_PAUSE | SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE |\
    SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK | SUPPORT_SEEK


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the squeezebox platform. """
    add_devices([
        SqueezeBoxDevice(
            config.get('name', 'SqueezeBox'),
            config.get('server'),
            config.get('player'),
            config.get('port', '9090'),
            config.get('user', None),
            config.get('password', None)
        )])


# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-public-methods
class SqueezeBoxDevice(MediaPlayerDevice):
    """ Represents a SqueezeBox device. """

    def __init__(self, name, server, player, port, user, password):
        super(SqueezeBoxDevice, self).__init__()
        self._name = name
        self._server = server
        self._player = player
        self._port = port
        self._user = user
        self._password = password
        self._status = {}
        self.update()
        self._http_port = self._query('pref', 'httpport', '?')

    @property
    def name(self):
        """ Returns the name of the device. """
        return self._name

    @property
    def state(self):
        """ Returns the state of the device. """
        if ('power' in self._status and self._status['power'] == '0'):
            return STATE_OFF
        if('mode' in self._status):
            if self._status['mode'] == 'pause':
                return STATE_PAUSED
            if self._status['mode'] == 'play':
                return STATE_PLAYING
            if self._status['mode'] == 'stop':
                return STATE_IDLE
        return STATE_UNKNOWN

    def update(self):
        if(self._user and self._password):
            self._query('login', self._user, self._password)
        self._get_status()

    def _query(self, *parameters):
        """ Send request and await response from server  """
        telnet = telnetlib.Telnet(self._server, self._port)
        message = '{}\n'.format(' '.join(parameters))
        telnet.write(message.encode('UTF-8'))
        response = telnet.read_until(b'\n', timeout=3)\
            .decode('UTF-8')\
            .split(' ')[-1]\
            .strip()
        telnet.write(b'exit\n')
        return urllib.parse.unquote(response)

    def _get_status(self):
        """ request status and parse result """
        #   (title) : Song title
        # Requested Information
        # a (artist): Artist name 'artist'
        # d (duration): Song duration in seconds 'duration'
        # K (artwork_url): URL to remote artwork
        tags = 'adK'
        new_status = {}
        telnet = telnetlib.Telnet(self._server, self._port)
        telnet.write('{player} status - 1 tags:{tags}\n'.format(
            player=self._player,
            tags=tags
            ).encode('UTF-8'))
        response = telnet.read_until(b'\n', timeout=3)\
            .decode('UTF-8')\
            .split(' ')
        telnet.write(b'exit\n')
        for item in response:
            parts = urllib.parse.unquote(item).partition(':')
            new_status[parts[0]] = parts[2]
        self._status = new_status

    @property
    def volume_level(self):
        """ Volume level of the media player (0..1). """
        if('mixer volume' in self._status):
            return int(self._status['mixer volume']) / 100.0

    @property
    def is_volume_muted(self):
        if('mixer volume' in self._status):
            return int(self._status['mixer volume']) < 0

    @property
    def media_content_id(self):
        """ Content ID of current playing media. """
        if('current_title' in self._status):
            return self._status['current_title']

    @property
    def media_content_type(self):
        """ Content type of current playing media. """
        return MEDIA_TYPE_MUSIC

    @property
    def media_duration(self):
        """ Duration of current playing media in seconds. """
        if('duration' in self._status):
            return int(float(self._status['duration']))

    @property
    def media_image_url(self):
        """ Image url of current playing media. """
        if('artwork_url' in self._status):
            return self._status['artwork_url']
        return 'http://{server}:{port}/music/current/cover.jpg?player={player}'\
            .format(
                server=self._server,
                port=self._http_port,
                player=self._player)

    @property
    def media_title(self):
        """ Title of current playing media. """
        if('artist' in self._status and 'title' in self._status):
            return '{artist} - {title}'.format(
                artist=self._status['artist'],
                title=self._status['title']
                )
        if('current_title' in self._status):
            return self._status['current_title']

    @property
    def supported_media_commands(self):
        """ Flags of media commands that are supported. """
        return SUPPORT_SQUEEZEBOX

    def turn_off(self):
        """ turn_off media player. """
        self._query(self._player, 'power', '0')
        self.update_ha_state()

    def volume_up(self):
        """ volume_up media player. """
        self._query(self._player, 'mixer', 'volume', '+5')
        self.update_ha_state()

    def volume_down(self):
        """ volume_down media player. """
        self._query(self._player, 'mixer', 'volume', '-5')
        self.update_ha_state()

    def set_volume_level(self, volume):
        """ set volume level, range 0..1. """
        volume_percent = str(int(volume*100))
        self._query(self._player, 'mixer', 'volume', volume_percent)
        self.update_ha_state()

    def mute_volume(self, mute):
        """ mute (true) or unmute (false) media player. """
        mute_numeric = '1' if mute else '0'
        self._query(self._player, 'mixer', 'muting', mute_numeric)
        self.update_ha_state()

    def media_play_pause(self):
        """ media_play_pause media player. """
        self._query(self._player, 'pause')
        self.update_ha_state()

    def media_play(self):
        """ media_play media player. """
        self._query(self._player, 'play')
        self.update_ha_state()

    def media_pause(self):
        """ media_pause media player. """
        self._query(self._player, 'pause', '0')
        self.update_ha_state()

    def media_next_track(self):
        """ Send next track command. """
        self._query(self._player, 'playlist', 'index', '+1')
        self.update_ha_state()

    def media_previous_track(self):
        """ Send next track command. """
        self._query(self._player, 'playlist', 'index', '-1')
        self.update_ha_state()

    def media_seek(self, position):
        """ Send seek command. """
        self._query(self._player, 'time', position)
        self.update_ha_state()

    def turn_on(self):
        """ turn the media player on. """
        self._query(self._player, 'power', '1')
        self.update_ha_state()

    def play_youtube(self, media_id):
        """ Plays a YouTube media. """
        raise NotImplementedError()
