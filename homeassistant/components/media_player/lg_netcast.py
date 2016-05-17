"""
Support for LG TV (Netcast 3 or 4).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.lgtv/
"""
from datetime import timedelta
from http.client import HTTPConnection
import logging
from xml.etree import ElementTree

import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.media_player import (
    SUPPORT_NEXT_TRACK, SUPPORT_PAUSE, SUPPORT_PREVIOUS_TRACK,
    SUPPORT_TURN_OFF, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_STEP,
    SUPPORT_SELECT_SOURCE, MEDIA_TYPE_CHANNEL, MediaPlayerDevice)
from homeassistant.const import (
    CONF_PLATFORM, CONF_HOST, CONF_NAME, CONF_ACCESS_TOKEN,
    STATE_OFF, STATE_PLAYING, STATE_PAUSED, STATE_UNKNOWN)
import homeassistant.util as util

_LOGGER = logging.getLogger(__name__)

SUPPORT_LGTV = SUPPORT_PAUSE | SUPPORT_VOLUME_STEP | \
               SUPPORT_VOLUME_MUTE | SUPPORT_PREVIOUS_TRACK | \
               SUPPORT_NEXT_TRACK | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(seconds=1)

DEFAULT_NAME = 'LG TV Remote'
DEFAULT_PORT = 8080

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): "lg_netcast",
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_ACCESS_TOKEN): vol.All(cv.string, vol.Length(max=6)),
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the LG TV platform."""
    add_devices([LgTVDevice(config)])


# pylint: disable=too-many-public-methods, abstract-method
# pylint: disable=too-many-instance-attributes
class LgTVDevice(MediaPlayerDevice):
    """Representation of a LG TV."""

    def __init__(self, config):
        """Initialize the LG TV device."""
        self._client = LgTVROAPClient(config)

        self._name = config[CONF_NAME]
        self._muted = False
        # Assume that the TV is in Play mode
        self._playing = True
        self._volume = 0
        self._channel_name = ''
        self._program_name = ''
        self._state = STATE_UNKNOWN
        self._sources = {}
        self._source_names = []

        self.update()

    def send_command(self, command):
        """Send remote control commands to the TV."""
        try:
            self._client.send_command(command)
        except OSError:
            self._state = STATE_OFF

    @util.Throttle(MIN_TIME_BETWEEN_SCANS, MIN_TIME_BETWEEN_FORCED_SCANS)
    def update(self):
        """Retrieve the latest data from the LG TV."""
        try:
            self._state = STATE_PLAYING
            volume_info = self._client.query_data(LG_QUERY_VOLUME_INFO)
            if volume_info:
                volume_info = volume_info[0]
                self._volume = float(volume_info.find(LG_DAT_LEVEL).text)
                self._muted = volume_info.find(LG_DAT_MUTE).text == 'true'

            channel_info = self._client.query_data(LG_QUERY_CUR_CHANNEL)
            if channel_info:
                channel_info = channel_info[0]
                self._channel_name = channel_info.find(LG_DAT_CH_NAME).text
                self._program_name = channel_info.find(LG_DAT_PROG_NAME).text

            channel_list = self._client.query_data(LG_QUERY_CHANNEL_LIST)
            if channel_list:
                channel_names = [str(c.find(LG_DAT_CH_NAME).text) for
                                 c in channel_list]
                self._sources = dict(zip(channel_names, channel_list))
                # sort source names by the major channel number
                source_tuples = [(k, self._sources[k].find(LG_DAT_MAJOR).text)
                                 for k in self._sources.keys()]
                sorted_sources = sorted(source_tuples,
                                        key=lambda channel: int(channel[1]))
                self._source_names = [n for n, k in sorted_sources]
        except OSError:
            self._state = STATE_OFF

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume / 100.0

    @property
    def source(self):
        """Return the current input source."""
        return self._channel_name

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_names

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MEDIA_TYPE_CHANNEL

    @property
    def media_channel(self):
        """Channel currently playing."""
        return self._channel_name

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._program_name

    @property
    def supported_media_commands(self):
        """Flag of media commands that are supported."""
        return SUPPORT_LGTV

    def turn_off(self):
        """Turn off media player."""
        self.send_command(LG_CMD_POWER)

    def volume_up(self):
        """Volume up the media player."""
        self.send_command(LG_CMD_VOL_UP)

    def volume_down(self):
        """Volume down media player."""
        self.send_command(LG_CMD_VOL_DOWN)

    def mute_volume(self, mute):
        """Send mute command."""
        self.send_command(LG_CMD_VOL_MUTE)

    def select_source(self, source):
        """Select input source."""
        self._client.change_channel(self._sources[source])

    def media_play_pause(self):
        """Simulate play pause media player."""
        if self._playing:
            self.media_pause()
        else:
            self.media_play()

    def media_play(self):
        """Send play command."""
        self._playing = True
        self._state = STATE_PLAYING
        self.send_command(LG_CMD_PLAY)

    def media_pause(self):
        """Send media pause command to media player."""
        self._playing = False
        self._state = STATE_PAUSED
        self.send_command(LG_CMD_PAUSE)

    def media_next_track(self):
        """Send next track command."""
        self.send_command(LG_CMD_FAST_FORWARD)

    def media_previous_track(self):
        """Send the previous track command."""
        self.send_command(LG_CMD_REWIND)


# LG TV remote control commands
LG_CMD_POWER = 1
LG_CMD_VOL_UP = 24
LG_CMD_VOL_DOWN = 25
LG_CMD_VOL_MUTE = 26
LG_CMD_PLAY = 33
LG_CMD_PAUSE = 34
LG_CMD_FAST_FORWARD = 36
LG_CMD_REWIND = 37
# LG TV data queries
LG_QUERY_VOLUME_INFO = 'volume_info'
LG_QUERY_CUR_CHANNEL = 'cur_channel'
LG_QUERY_CHANNEL_LIST = 'channel_list'
# LG TV data fields
# volume
LG_DAT_MUTE = 'mute'
LG_DAT_LEVEL = 'level'
# channels
LG_DAT_MAJOR = 'major'
LG_DAT_CH_NAME = 'chname'
LG_DAT_PROG_NAME = 'progName'


class LgTVROAPClient(object):
    """LG TV client using the ROAP protocol.

    The client is inspired by the work of
    https://github.com/ubaransel/lgcommander
    """

    HEADER = {"Content-Type": "application/atom+xml"}
    XML = '<?xml version=\"1.0\" encoding=\"utf-8\"?>'
    KEY = XML + '<auth><type>AuthKeyReq</type></auth>'
    AUTH = XML + '<auth><type>%s</type><value>%s</value></auth>'
    COMMAND = XML + '<command><session>%s</session><type>%s</type>%s</command>'

    def __init__(self, config):
        """Initialize the LG TV client."""
        self.host = config[CONF_HOST]
        self.access_token = config[CONF_ACCESS_TOKEN] if \
            CONF_ACCESS_TOKEN in config else None
        self.session = None

    def send_command(self, command):
        """Send remote control commands to the TV."""
        if not self.session:
            self.session = self._get_session_id()
        if self.session:
            message = self.COMMAND % (self.session, 'HandleKeyInput',
                                      '<value>%s</value>' % command)
            self._send_to_tv(message, 'command')

    def change_channel(self, channel):
        """Send change channel command to the TV."""
        if not self.session:
            self.session = self._get_session_id()
        if self.session:
            message = self.COMMAND % (self.session, 'HandleChannelChange',
                                      ElementTree.tostring(channel,
                                                           encoding="unicode"))
            self._send_to_tv(message, 'command')

    def query_data(self, query):
        """Query status information from the TV."""
        if not self.session:
            self.session = self._get_session_id()
        if self.session:
            http_response = self._send_to_tv(None, 'data?target=%s' % query)
            if http_response and http_response.reason == 'OK':
                data = http_response.read()
                tree = ElementTree.XML(data)
                data_list = []
                for data in tree.iter('data'):
                    data_list.append(data)
                return data_list

    def _get_session_id(self):
        """Get the session key for the TV connection.

        If a pair key is defined the session id is requested otherwise display
        the pair key on TV.
        """
        if not self.access_token:
            self._display_pair_key()
            return
        message = self.AUTH % ('AuthReq', self.access_token)
        http_response = self._send_to_tv(message, 'auth')
        if http_response and http_response.reason != "OK":
            return
        data = http_response.read()
        tree = ElementTree.XML(data)
        session = tree.find('session').text
        if len(session) >= 8:
            return session

    def _display_pair_key(self):
        """Send message to display the pair key on TV screen."""
        self._send_to_tv(self.KEY, 'auth')

    def _send_to_tv(self, message, message_type):
        """Send message of given type to the tv."""
        conn = HTTPConnection(self.host, port=DEFAULT_PORT, timeout=3)
        if message:
            conn.request("POST", "/roap/api/%s" % message_type, message,
                         headers=self.HEADER)
        else:
            conn.request("GET", "/roap/api/%s" % message_type,
                         headers=self.HEADER)
        return conn.getresponse()
