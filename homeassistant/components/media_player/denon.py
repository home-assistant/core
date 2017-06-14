"""
Support for Denon Network Receivers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.denon/
"""
import logging
import telnetlib

import voluptuous as vol

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA, SUPPORT_NEXT_TRACK, SUPPORT_SELECT_SOURCE,
    SUPPORT_PAUSE, SUPPORT_PREVIOUS_TRACK, SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    SUPPORT_STOP, SUPPORT_PLAY, MediaPlayerDevice)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, STATE_OFF, STATE_ON, STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Music station'

SUPPORT_DENON = SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
    SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE \

SUPPORT_MEDIA_MODES = SUPPORT_PAUSE | SUPPORT_STOP | \
    SUPPORT_PREVIOUS_TRACK | SUPPORT_NEXT_TRACK | SUPPORT_PLAY

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

NORMAL_INPUTS = {'Cd': 'CD', 'Dvd': 'DVD', 'Blue ray': 'BD', 'TV': 'TV',
                 'Satelite / Cable': 'SAT/CBL', 'Game': 'GAME',
                 'Game2': 'GAME2', 'Video Aux': 'V.AUX', 'Dock': 'DOCK'}

MEDIA_MODES = {'Tuner': 'TUNER', 'Media server': 'SERVER',
               'Ipod dock': 'IPOD', 'Net/USB': 'NET/USB',
               'Rapsody': 'RHAPSODY', 'Napster': 'NAPSTER',
               'Pandora': 'PANDORA', 'LastFM': 'LASTFM',
               'Flickr': 'FLICKR', 'Favorites': 'FAVORITES',
               'Internet Radio': 'IRADIO', 'USB/IPOD': 'USB/IPOD'}

# Sub-modes of 'NET/USB'
# {'USB': 'USB', 'iPod Direct': 'IPD', 'Internet Radio': 'IRP',
#  'Favorites': 'FVP'}


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Denon platform."""
    denon = DenonDevice(config.get(CONF_NAME), config.get(CONF_HOST))

    if denon.update():
        add_devices([denon])
        return True
    else:
        return False


class DenonDevice(MediaPlayerDevice):
    """Representation of a Denon device."""

    def __init__(self, name, host):
        """Initialize the Denon device."""
        self._name = name
        self._host = host
        self._pwstate = 'PWSTANDBY'
        self._volume = 0
        # Initial value 60dB, changed if we get a MVMAX
        self._volume_max = 60
        self._source_list = NORMAL_INPUTS.copy()
        self._source_list.update(MEDIA_MODES)
        self._muted = False
        self._mediasource = ''
        self._mediainfo = ''

        self._should_setup_sources = True

    def _setup_sources(self, telnet):
        # NSFRN - Network name
        self._name = self.telnet_request(telnet, 'NSFRN ?')[len('NSFRN '):]

        # SSFUN - Configured sources with names
        self._source_list = {}
        for line in self.telnet_request(telnet, 'SSFUN ?', all_lines=True):
            source, configured_name = line[len('SSFUN'):].split(" ", 1)
            self._source_list[configured_name] = source

        # SSSOD - Deleted sources
        for line in self.telnet_request(telnet, 'SSSOD ?', all_lines=True):
            source, status = line[len('SSSOD'):].split(" ", 1)
            if status == 'DEL':
                for pretty_name, name in self._source_list.items():
                    if source == name:
                        del self._source_list[pretty_name]
                        break

    @classmethod
    def telnet_request(cls, telnet, command, all_lines=False):
        """Execute `command` and return the response."""
        _LOGGER.debug("Sending: %s", command)
        telnet.write(command.encode('ASCII') + b'\r')
        lines = []
        while True:
            line = telnet.read_until(b'\r', timeout=0.2)
            if not line:
                break
            lines.append(line.decode('ASCII').strip())
            _LOGGER.debug("Recived: %s", line)

        if all_lines:
            return lines
        return lines[0]

    def telnet_command(self, command):
        """Establish a telnet connection and sends `command`."""
        telnet = telnetlib.Telnet(self._host)
        _LOGGER.debug("Sending: %s", command)
        telnet.write(command.encode('ASCII') + b'\r')
        telnet.read_very_eager()  # skip response
        telnet.close()

    def update(self):
        """Get the latest details from the device."""
        try:
            telnet = telnetlib.Telnet(self._host)
        except OSError:
            return False

        if self._should_setup_sources:
            self._setup_sources(telnet)
            self._should_setup_sources = False

        self._pwstate = self.telnet_request(telnet, 'PW?')
        for line in self.telnet_request(telnet, 'MV?', all_lines=True):
            if line.startswith('MVMAX '):
                # only grab two digit max, don't care about any half digit
                self._volume_max = int(line[len('MVMAX '):len('MVMAX XX')])
                continue
            if line.startswith('MV'):
                self._volume = int(line[len('MV'):])
        self._muted = (self.telnet_request(telnet, 'MU?') == 'MUON')
        self._mediasource = self.telnet_request(telnet, 'SI?')[len('SI'):]

        if self._mediasource in MEDIA_MODES.values():
            self._mediainfo = ""
            answer_codes = ["NSE0", "NSE1X", "NSE2X", "NSE3X", "NSE4", "NSE5",
                            "NSE6", "NSE7", "NSE8"]
            for line in self.telnet_request(telnet, 'NSE', all_lines=True):
                self._mediainfo += line[len(answer_codes.pop(0)):] + '\n'
        else:
            self._mediainfo = self.source

        telnet.close()
        return True

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        if self._pwstate == 'PWSTANDBY':
            return STATE_OFF
        if self._pwstate == 'PWON':
            return STATE_ON

        return STATE_UNKNOWN

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume / self._volume_max

    @property
    def is_volume_muted(self):
        """Return boolean if volume is currently muted."""
        return self._muted

    @property
    def source_list(self):
        """Return the list of available input sources."""
        return sorted(list(self._source_list.keys()))

    @property
    def media_title(self):
        """Return the current media info."""
        return self._mediainfo

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        if self._mediasource in MEDIA_MODES.values():
            return SUPPORT_DENON | SUPPORT_MEDIA_MODES
        else:
            return SUPPORT_DENON

    @property
    def source(self):
        """Return the current input source."""
        for pretty_name, name in self._source_list.items():
            if self._mediasource == name:
                return pretty_name

    def turn_off(self):
        """Turn off media player."""
        self.telnet_command('PWSTANDBY')

    def volume_up(self):
        """Volume up media player."""
        self.telnet_command('MVUP')

    def volume_down(self):
        """Volume down media player."""
        self.telnet_command('MVDOWN')

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self.telnet_command('MV' +
                            str(round(volume * self._volume_max)).zfill(2))

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        self.telnet_command('MU' + ('ON' if mute else 'OFF'))

    def media_play(self):
        """Play media media player."""
        self.telnet_command('NS9A')

    def media_pause(self):
        """Pause media player."""
        self.telnet_command('NS9B')

    def media_stop(self):
        """Pause media player."""
        self.telnet_command('NS9C')

    def media_next_track(self):
        """Send the next track command."""
        self.telnet_command('NS9D')

    def media_previous_track(self):
        """Send the previous track command."""
        self.telnet_command('NS9E')

    def turn_on(self):
        """Turn the media player on."""
        self.telnet_command('PWON')

    def select_source(self, source):
        """Select input source."""
        self.telnet_command('SI' + self._source_list.get(source))
