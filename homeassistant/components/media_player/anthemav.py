"""
Support for Anthem Network Receivers and Processors

"""
import logging
import telnetlib
import re

import voluptuous as vol

DOMAIN = 'anthemav'

from homeassistant.components.media_player import (
    PLATFORM_SCHEMA, SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_SELECT_SOURCE,
    SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET, MediaPlayerDevice)
from homeassistant.const import (
    CONF_NAME, CONF_HOST, CONF_PORT, STATE_OFF, STATE_ON, STATE_UNKNOWN)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_PORT): cv.port,
    })

SUPPORT_ANTHEMAV = SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
    SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE

VIDEO_FORMATS = {'0': 'No Video', '1': 'Other Video', '2': '1080p60',
        '3': '1080p50', '4': '1080p24', '5': '1080i60', '6': '1080i50',
        '7': '720p60', '8': '720p50', '9': '576p50', '10': '576i50',
        '11': '480p60', '12': '480i60', '13': '3D', '14': '4K'}

AUDIO_MODES = {'00': 'None', '01': 'AnthemLogic-Movie', '02': 'AnthemLogic-Music',
        '03': 'PLIIx Movie', '04': 'PLIIx Music', '05': 'Neo:6 Cinema',
        '06': 'Neo:6 Music', '07': 'All Channel Stereo', 
        '08': 'All Channel Mono', '09': 'Mono', '10': 'Mono-Academy',
        '11': 'Mono(L)', '12': 'Mono(R)', '13': 'High Blend',
        '14': 'Dolby Surround', '15': 'Neo:X-Cinema',
        '16': 'Neo:X-Music'}

AUDIO_FORMATS = {'0': 'No Input', '1': 'Analog', '2': 'PCM', '3': 'Dolby',
        '4': 'DSD', '5': 'DTS', '6': 'Atmos'}

AUDIO_CHANNELS = {'0': 'No Input', '1': 'Other', '2': 'Mono', '3': '2.0',
        '4': '5.1', '5': '6.1', '6': '7.1', '7': 'Atmos'}

def setup_platform(hass, config, add_devices, discovery_info=None):
    anthemav = AnthemAVR(config.get(CONF_NAME), config.get(CONF_HOST), config.get(CONF_PORT))

    if anthemav.update():
        add_devices([anthemav])
        _LOGGER.debug('setup_platform was successful')
        return True
    else:
        _LOGGER.debug('setup_platform failed')
        return False

class AnthemAVR(MediaPlayerDevice):
    def __init__(self, name, host, port):
        """Initialize the Denon device."""
        self._name = name
        self._host = host
        self._port = port
        self._pwstate = 'PWSTANDBY'
        self._volume = 0.00
        self._attenuation = 0
        self._muted = False
        self._input_count = 0
        self._input_list = {}
        self._should_setup_inputs = True
        self._selected_source = ''
        self._source_name_to_number = {}
        self._source_number_to_name = {}
        self._video_formats = VIDEO_FORMATS.copy()
        self._audio_modes = AUDIO_MODES.copy()

        _LOGGER.debug('class __init__ successful')

    def _setup_inputs(self, telnet):
        _LOGGER.info('Setting up Anthem Inputs')
        ic = self.telnet_query(telnet, 'ICN')
        if ic :
            self._input_count = int(ic)
            for source_number in range(1,self._input_count+1):
                source_name = self.telnet_query(telnet, 'ISN'+str(source_number).zfill(2))
                self._source_name_to_number[source_name] = source_number
                self._source_number_to_name[source_number] = source_name
                self._should_setup_inputs = False

    @classmethod
    def telnet_query(cls, telnet, code):
        telnet.write(code.encode('ASCII') + b'?;\r')
        lines = []
        while True:
            line = telnet.read_until(b';', timeout=0.2)
            if not line:
                break
            lines.append(line.decode('ASCII').strip())

        for resp in lines:
            m = re.match("^"+code+"([^;]+);",resp)
            if m:
                _LOGGER.debug("Telnet polled value for %s is %s",code,m.group(1))
                return m.group(1)

        return 

    def telnet_command(self, command):
        try:
            telnet = telnetlib.Telnet(self._host,self._port)
        except OSError:
            _LOGGER.error('Unable to connect to Anthem control port')
            return False

        _LOGGER.debug('Sending: "%s"', command)
        telnet.write(command.encode('ASCII') + b';\r')
        telnet.read_very_eager()  # skip response
        telnet.close()

    def update(self):
        """Get the latest details from the device."""
        try:
            telnet = telnetlib.Telnet(self._host,self._port)
        except OSError:
            _LOGGER.error('Unable to connect to Anthem control port')
            return False

        self._name = self.telnet_query(telnet, 'IDM')
        self._pwstate = self.telnet_query(telnet, 'Z1POW')

        if self._pwstate != '1':
            self._muted = False
            self._volume = 0
        else:
            self._muted = (self.telnet_query(telnet, 'Z1MUT') == '1')

            self._attenuation = self.telnet_query(telnet, 'Z1VOL')
            if self._attenuation:
                self._volume = (90.00 + int(self._attenuation)) / 90
            else:
                self._volume = 0

            if self._should_setup_inputs:
                self._setup_inputs(telnet)

            source_number = int(self.telnet_query(telnet,'Z1INP'))

            if source_number:
                self._selected_source = self._source_number_to_name.get(source_number)
            else:
                self._selected_source = None

            self._format_video = self.telnet_query(telnet, 'Z1VIR')
            self._format_audio = self.telnet_query(telnet, 'Z1AIN')
            self._audo_channels = self.telnet_query(telnet, 'Z1AIC')
            self._audio_mode = self.telnet_query(telnet, 'Z1ALM')

        telnet.close()
        return True

    @property
    def supported_media_commands(self):
        return SUPPORT_ANTHEMAV

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        if self._pwstate == '0':
            return STATE_OFF
        if self._pwstate == '1':
            return STATE_ON

        return STATE_UNKNOWN

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    def turn_off(self):
        """Turn off media player."""
        self.telnet_command('Z1POW0')

    def turn_on(self):
        """Turn the media player on."""
        self.telnet_command('Z1POW1;Z1POW')

    def volume_up(self):
        """Volume up media player."""
        self.telnet_command('Z1VUP01')

    def volume_down(self):
        """Volume down media player."""
        self.telnet_command('Z1VDN01')

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        _LOGGER.debug('Request to set volume to %f',volume)
        setatt = (-90 * volume)
        _LOGGER.debug('Desired attenuation is %d',setatt)
        self.telnet_command('Z1VOL-49')

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        self.telnet_command('Z1MUT' + ('1' if mute else '0'))

    @property
    def media_title(self):
        """Title of current playing media."""
        return self._selected_source

    @property
    def app_name(self):
        out_video = self._video_formats[self._format_video] if self._video_formats[self._format_video] else 'Unknown Video'
        out_audio = self._format_audio if self._format_audio else 'Unknown Audio'
        out_mode = self._audio_modes[self._audio_mode] if self._audio_modes[self._audio_mode] else 'Unknown Mode'
        return out_video+' / '+out_audio+' ('+out_mode+')'

    @property
    def source(self):
        """Return the current input source."""
        return self._selected_source

    @property
    def source_list(self):
        """List of available input sources."""
        return list(self._source_name_to_number.keys())

    def select_source(self, source):
        """Select input source."""
        self.telnet_command('Z1INP'+self._source_name_to_number.get(source))
