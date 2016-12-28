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
        _LOGGER.debug('class __init__ successful')

    def _setup_inputs(self, telnet):
        _LOGGER.info('Setting up Anthem Inputs')
        self._input_count = int(self.telnet_query(telnet, 'ICN'))
        for source_number in range(1,self._input_count+1):
            source_name = self.telnet_query(telnet, 'ISN'+str(source_number).zfill(2))

            self._source_name_to_number[source_name] = source_number
            self._source_number_to_name[source_number] = source_name

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
                self._should_setup_inputs = False

            source_number = int(self.telnet_query(telnet,'Z1INP'))

            if source_number:
                self._selected_source = self._source_number_to_name.get(source_number)
            else:
                self._selected_source = None

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
