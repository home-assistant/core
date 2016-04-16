"""
Support for interfacing to the Logitech SqueezeBox API.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.squeezebox/
"""
import logging
import telnetlib
import urllib.parse

from homeassistant.components.media_player import (
    DOMAIN, MEDIA_TYPE_MUSIC, SUPPORT_NEXT_TRACK, SUPPORT_PAUSE,
    SUPPORT_PREVIOUS_TRACK, SUPPORT_SEEK, SUPPORT_TURN_OFF, SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET, MediaPlayerDevice)
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME, STATE_IDLE, STATE_OFF,
    STATE_PAUSED, STATE_PLAYING, STATE_UNKNOWN)

_LOGGER = logging.getLogger(__name__)

SUPPORT_SQUEEZEBOX = SUPPORT_PAUSE | SUPPORT_VOLUME_SET | \
    SUPPORT_VOLUME_MUTE | SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK | \
    SUPPORT_SEEK | SUPPORT_TURN_ON | SUPPORT_TURN_OFF

KNOWN_DEVICES = []


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the squeezebox platform."""
    if discovery_info is not None:
        host = discovery_info[0]
        port = 9090
    else:
        host = config.get(CONF_HOST)
        port = int(config.get('port', 9090))

    if not host:
        _LOGGER.error(
            "Missing required configuration items in %s: %s",
            DOMAIN,
            CONF_HOST)
        return False

    # Only add a media server once
    if host in KNOWN_DEVICES:
        return False
    KNOWN_DEVICES.append(host)

    lms = LogitechMediaServer(
        host, port,
        config.get(CONF_USERNAME),
        config.get(CONF_PASSWORD))

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
        http_port = None
        try:
            http_port = self.query('pref', 'httpport', '?')
            if not http_port:
                _LOGGER.error(
                    "Unable to read data from server %s:%s",
                    self.host,
                    self.port)
                return
            return http_port
        except ConnectionError as ex:
            _LOGGER.error(
                "Failed to connect to server %s:%s - %s",
                self.host,
                self.port,
                ex)
            return

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

    def get_player_status(self, player):
        """Get ithe status of a player."""
        #   (title) : Song title
        # Requested Information
        # a (artist): Artist name 'artist'
        # d (duration): Song duration in seconds 'duration'
        # K (artwork_url): URL to remote artwork
        tags = 'adK'
        new_status = {}
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
