"""
Support for interfacing to the Logitech SqueezeBox API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.squeezebox/
"""
import logging
import telnetlib
import urllib.parse

import voluptuous as vol

from homeassistant.components.media_player import (
    ATTR_MEDIA_ENQUEUE, SUPPORT_PLAY_MEDIA,
    MEDIA_TYPE_MUSIC, SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, PLATFORM_SCHEMA,
    SUPPORT_PREVIOUS_TRACK, SUPPORT_SEEK, SUPPORT_TURN_OFF, SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET, MediaPlayerDevice)
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME, STATE_IDLE, STATE_OFF,
    STATE_PAUSED, STATE_PLAYING, STATE_UNKNOWN, CONF_PORT)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 9090

KNOWN_DEVICES = []

SUPPORT_SQUEEZEBOX = SUPPORT_PAUSE | SUPPORT_VOLUME_SET | \
    SUPPORT_VOLUME_MUTE | SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK | \
    SUPPORT_SEEK | SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_PLAY_MEDIA

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
    vol.Optional(CONF_USERNAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the squeezebox platform."""
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)

    if discovery_info is not None:
        host = discovery_info[0]
        port = DEFAULT_PORT
    else:
        host = config.get(CONF_HOST)
        port = config.get(CONF_PORT)

    # Only add a media server once
    if host in KNOWN_DEVICES:
        return False
    KNOWN_DEVICES.append(host)

    lms = LogitechMediaServer(host, port, username, password)

    if not lms.init_success:
        return False

    add_devices(lms.create_players())

    return True


class LogitechMediaServer(object):
    """Representation of a Logitech media server."""

    def __init__(self, host, port, username, password):
        """Initialize the Logitech device."""
        self.host = host
        self.port = port
        self._username = username
        self._password = password
        self.http_port = self._get_http_port()
        self.init_success = True if self.http_port else False

    def _get_http_port(self):
        """Get http port from media server, it is used to get cover art."""
        http_port = self.query('pref', 'httpport', '?')
        if not http_port:
            _LOGGER.error("Failed to connect to server %s:%s",
                          self.host, self.port)
        return http_port

    def create_players(self):
        """Create a list of SqueezeBoxDevices connected to the LMS."""
        players = []
        count = self.query('player', 'count', '?')
        for index in range(0, int(count)):
            player_id = self.query('player', 'id', str(index), '?')
            player = SqueezeBoxDevice(self, player_id)
            players.append(player)
        return players

    def query(self, *parameters):
        """Send request and await response from server."""
        try:
            telnet = telnetlib.Telnet(self.host, self.port)
            if self._username and self._password:
                telnet.write('login {username} {password}\n'.format(
                    username=self._username,
                    password=self._password).encode('UTF-8'))
                telnet.read_until(b'\n', timeout=3)
            message = '{}\n'.format(' '.join(parameters))
            telnet.write(message.encode('UTF-8'))
            response = telnet.read_until(b'\n', timeout=3)\
                             .decode('UTF-8')\
                             .split(' ')[-1]\
                             .strip()
            telnet.write(b'exit\n')
            return urllib.parse.unquote(response)
        except (OSError, ConnectionError) as error:
            _LOGGER.error("Could not communicate with %s:%d: %s",
                          self.host,
                          self.port,
                          error)
            return None

    def get_player_status(self, player):
        """Get ithe status of a player."""
        #   (title) : Song title
        # Requested Information
        # a (artist): Artist name 'artist'
        # d (duration): Song duration in seconds 'duration'
        # K (artwork_url): URL to remote artwork
        tags = 'adK'
        new_status = {}
        try:
            telnet = telnetlib.Telnet(self.host, self.port)
            telnet.write('{player} status - 1 tags:{tags}\n'.format(
                player=player,
                tags=tags
            ).encode('UTF-8'))
            response = telnet.read_until(b'\n', timeout=3)\
                             .decode('UTF-8')\
                             .split(' ')
            telnet.write(b'exit\n')
            for item in response:
                parts = urllib.parse.unquote(item).partition(':')
                new_status[parts[0]] = parts[2]
        except (OSError, ConnectionError) as error:
            _LOGGER.error("Could not communicate with %s:%d: %s",
                          self.host,
                          self.port,
                          error)
        return new_status


# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-public-methods
class SqueezeBoxDevice(MediaPlayerDevice):
    """Representation of a SqueezeBox device."""

    # pylint: disable=too-many-arguments, abstract-method
    def __init__(self, lms, player_id):
        """Initialize the SqeezeBox device."""
        super(SqueezeBoxDevice, self).__init__()
        self._lms = lms
        self._id = player_id
        self._name = self._lms.query(self._id, 'name', '?')
        self._status = self._lms.get_player_status(self._id)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        if 'power' in self._status and self._status['power'] == '0':
            return STATE_OFF
        if 'mode' in self._status:
            if self._status['mode'] == 'pause':
                return STATE_PAUSED
            if self._status['mode'] == 'play':
                return STATE_PLAYING
            if self._status['mode'] == 'stop':
                return STATE_IDLE
        return STATE_UNKNOWN

    def update(self):
        """Retrieve latest state."""
        self._status = self._lms.get_player_status(self._id)

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        if 'mixer volume' in self._status:
            return int(float(self._status['mixer volume'])) / 100.0

    @property
    def is_volume_muted(self):
        """Return true if volume is muted."""
        if 'mixer volume' in self._status:
            return self._status['mixer volume'].startswith('-')

    @property
    def media_content_id(self):
        """Content ID of current playing media."""
        if 'current_title' in self._status:
            return self._status['current_title']

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_MUSIC

    @property
    def media_duration(self):
        """Duration of current playing media in seconds."""
        if 'duration' in self._status:
            return int(float(self._status['duration']))

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        if 'artwork_url' in self._status:
            media_url = self._status['artwork_url']
        elif 'id' in self._status:
            media_url = ('/music/{track_id}/cover.jpg').format(
                track_id=self._status['id'])
        else:
            media_url = ('/music/current/cover.jpg?player={player}').format(
                player=self._id)

        base_url = 'http://{server}:{port}/'.format(
            server=self._lms.host,
            port=self._lms.http_port)

        return urllib.parse.urljoin(base_url, media_url)

    @property
    def media_title(self):
        """Title of current playing media."""
        if 'artist' in self._status and 'title' in self._status:
            return '{artist} - {title}'.format(
                artist=self._status['artist'],
                title=self._status['title']
                )
        if 'current_title' in self._status:
            return self._status['current_title']

    @property
    def supported_media_commands(self):
        """Flag of media commands that are supported."""
        return SUPPORT_SQUEEZEBOX

    def turn_off(self):
        """Turn off media player."""
        self._lms.query(self._id, 'power', '0')
        self.update_ha_state()

    def volume_up(self):
        """Volume up media player."""
        self._lms.query(self._id, 'mixer', 'volume', '+5')
        self.update_ha_state()

    def volume_down(self):
        """Volume down media player."""
        self._lms.query(self._id, 'mixer', 'volume', '-5')
        self.update_ha_state()

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        volume_percent = str(int(volume*100))
        self._lms.query(self._id, 'mixer', 'volume', volume_percent)
        self.update_ha_state()

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        mute_numeric = '1' if mute else '0'
        self._lms.query(self._id, 'mixer', 'muting', mute_numeric)
        self.update_ha_state()

    def media_play_pause(self):
        """Send pause command to media player."""
        self._lms.query(self._id, 'pause')
        self.update_ha_state()

    def media_play(self):
        """Send play command to media player."""
        self._lms.query(self._id, 'play')
        self.update_ha_state()

    def media_pause(self):
        """Send pause command to media player."""
        self._lms.query(self._id, 'pause', '1')
        self.update_ha_state()

    def media_next_track(self):
        """Send next track command."""
        self._lms.query(self._id, 'playlist', 'index', '+1')
        self.update_ha_state()

    def media_previous_track(self):
        """Send next track command."""
        self._lms.query(self._id, 'playlist', 'index', '-1')
        self.update_ha_state()

    def media_seek(self, position):
        """Send seek command."""
        self._lms.query(self._id, 'time', position)
        self.update_ha_state()

    def turn_on(self):
        """Turn the media player on."""
        self._lms.query(self._id, 'power', '1')
        self.update_ha_state()

    def play_media(self, media_type, media_id, **kwargs):
        """
        Send the play_media command to the media player.

        If ATTR_MEDIA_ENQUEUE is True, add `media_id` to the current playlist.
        """
        if kwargs.get(ATTR_MEDIA_ENQUEUE):
            self._add_uri_to_playlist(media_id)
        else:
            self._play_uri(media_id)

    def _play_uri(self, media_id):
        """
        Replace the current play list with the uri.

        Telnet Command Strucutre:
        <playerid> playlist play <item> <title> <fadeInSecs>

        The "playlist play" command puts the specified song URL,
        playlist or directory contents into the current playlist
        and plays starting at the first item. Any songs previously
        in the playlist are discarded. An optional title value may be
        passed to set a title. This can be useful for remote URLs.
        The "fadeInSecs" parameter may be passed to specify fade-in period.

        Examples:
        Request: "04:20:00:12:23:45 playlist play
                    /music/abba/01_Voulez_Vous.mp3<LF>"
        Response: "04:20:00:12:23:45 playlist play
            /music/abba/01_Voulez_Vous.mp3<LF>"

        """
        self._lms.query(self._id, 'playlist', 'play', media_id)
        self.update_ha_state()

    def _add_uri_to_playlist(self, media_id):
        """
        Add a items to the existing playlist.

        Telnet Command Strucutre:
        <playerid> playlist add <item>

        The "playlist add" command adds the specified song URL, playlist or
        directory contents to the end of the current playlist. Songs
        currently playing or already on the playlist are not affected.

        Examples:
        Request: "04:20:00:12:23:45 playlist add
            /music/abba/01_Voulez_Vous.mp3<LF>"
        Response: "04:20:00:12:23:45 playlist add
            /music/abba/01_Voulez_Vous.mp3<LF>"

        Request: "04:20:00:12:23:45 playlist add
            /playlists/abba.m3u<LF>"
        Response: "04:20:00:12:23:45 playlist add
            /playlists/abba.m3u<LF>"

        """
        self._lms.query(self._id, 'playlist', 'add', media_id)
        self.update_ha_state()
