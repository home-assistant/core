"""
Support for Onkyo Receivers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.onkyo/
"""
import logging
import threading
import re

import voluptuous as vol

from homeassistant.components.media_player import (
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    SUPPORT_SELECT_SOURCE, SUPPORT_PLAY, MediaPlayerDevice, PLATFORM_SCHEMA)
from homeassistant.const import (STATE_OFF, STATE_ON, CONF_HOST, CONF_NAME)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = []

_LOGGER = logging.getLogger(__name__)

CONF_SOURCES = 'sources'

DEFAULT_NAME = 'Onkyo Serial Receiver'

SUPPORT_ONKYO = SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
    SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE | SUPPORT_PLAY

KNOWN_HOSTS = []  # type: List[str]
CONF_ZONES = 'zones'
CONF_PORT = 'port'
ZONE_SETUP_SCHEMA = vol.Schema({
    vol.Required('commands'): vol.Schema({vol.All(cv.string): vol.Any(cv.string)}),
    vol.Required('queries'): vol.Schema({vol.All(cv.string): vol.Any(cv.string)})
})
ZONE_SCHEMA = vol.Schema({ vol.All(cv.string): ZONE_SETUP_SCHEMA })

DEFAULT_SOURCES = {
    "00": "VIDEO1,VCR/DVR,STB/DVR",
    "01": "VIDEO2,CBL/SAT",
    "02": "VIDEO3,GAME/TV,GAME,GAME1",
    "03": "VIDEO4,AUX1,AUX",
    "04": "VIDEO5,AUX2,GAME2",
    "05": "VIDEO6,PC",
    "06": "VIDEO7",
    "07": "Hidden1,EXTRA1",
    "08": "Hidden2,EXTRA2",
    "09": "Hidden3,EXTRA3",
    "10": "DVD,BD/DVD",
    "20": "TAPE,TAPE(1),TV/TAPE",
    "21": "TAPE2",
    "22": "PHONO",
    "23": "CD,TV/CD",
    "24": "FM",
    "25": "AM",
    "26": "TUNER",
    "27": "MUSIC SERVER,P4S,DLNA*2",
    "28": "INTERNET RADIO,iRadio Favorite*3",
    "29": "USB/USB (Front)",
    "2A": "USB (Rear)",
    "2B": "NETWORK,NET",
    "2C": "USB (toggle)",
    "2D": "Aiplay",
    "40": "UniversalPORT",
    "30": "MULTICH",
    "31": "XM*1",
    "32": "SIRIUS*1",
    "33": "DAB*5"
}

'''
Example Format:

media_player:
    platform: onkyo_serial
    port: '/dev/ttyUSB0'
    zones:
        master:
            commands:
                power: 'MPW'
            queries:
                volume: 'MVL'

        zone2:
            commands:
                power: 'ZPW'
            queries:
                volume: 'ZVOL'
'''

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PORT): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_ZONES): ZONE_SCHEMA,
    vol.Optional(CONF_SOURCES, default=DEFAULT_SOURCES): {cv.string: cv.string},
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Onkyo platform."""
    import serial
    import threading

    port = config.get(CONF_PORT)

    ser = serial.Serial(
        port=port,
        baudrate=9600,
        timeout=10,
        rtscts=0,
        xonxoff=0
    )

    devices = []
    zones = {}

    if ser:
        if CONF_ZONES in config:
            for key, value in config[CONF_ZONES].items():
                zones[key] = OnkyoSerialDevice(ser, config.get(CONF_SOURCES), value, name="onkyo-{zone}".format(zone=key))
                devices.append(zones[key])
    else:
        _LOGGER.error('Unable to connect to serial port %s', port)

    commands = {}
    for key, value in config[CONF_ZONES].items():
        commands[key] = config[CONF_ZONES][key]['commands']

    update_thread = OnkyoBackgroundWorker(ser, commands, zones)
    update_thread.start()
    add_devices(devices)


class OnkyoBackgroundWorker(threading.Thread):
    def __init__(self, port, commands, devices):
        threading.Thread.__init__(self)
        self.daemon = True
        self._port = port
        self._commands = commands
        self._devices = devices
        self._pattern = '\!1([A-Z]{3})(.{2})?'

        self.messages = {
            'power': self.power,
            'volume': self.volume,
            'source': self.source,
            'mute': self.mute
        }

    def _readline(self):
        eol = b'\x1a'
        leneol = len(eol)
        line = bytearray()
        while True:
            c = self._port.read(1)
            if c:
                line += c
                if line[-leneol:] == eol:
                    break
            else:
                break

        return bytes(line)

    def process(self, message, value):
        return self.messages[message](value)

    def power(self, value):
        if value == '00':
            return STATE_OFF
        else:
            return STATE_ON

    def mute(self, value):
        return value == '01'

    def volume(self, value):
        return int(value, 16) / 100

    def source(self, value):
        return DEFAULT_SOURCES[value]

    def run(self):
        while True:
            out = self._readline().decode('utf-8')
            match = re.search(self._pattern, out)
            if match:
                cmd = match.group(1)
                val = match.group(2)
                zone = None
                prop = None

                for z,c in self._commands.items():
                    for child_key,child_cmd in self._commands[z].items():
                        if child_cmd == cmd:
                            zone = z
                            prop = child_key
                            break

                if zone and prop:
                    device = self._devices[zone]
                    device.__dict__['_' + prop] = self.process(prop, val)


class OnkyoSerialDevice(MediaPlayerDevice):
    """Representation of an Onkyo device."""

    def __init__(self, port, sources, cmdquery, name=None):
        """Initialize the Onkyo Receiver."""
        self._port = port
        self._commands = cmdquery['commands']
        self._queries = cmdquery['queries']
        self._muted = False
        self._volume = 0
        self._source = None
        self._power = STATE_OFF
        self._name = name
        self._current_source = None
        self._source_list = list(sources.values())
        self._source_mapping = sources
        self._reverse_mapping = {value: key for key, value in sources.items()}
        self.update()

    def command(self, command):
        if self._port.isOpen():
            out = ''.join(['!1', command, '\r'])
            self._port.write(str.encode(out))
        else:
            return False
        return True

    def update(self):
        for query, cmd in self._queries.items():
            self.command(cmd)

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._power

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._muted

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_ONKYO

    @property
    def source(self):
        """"Return the current input source of the device."""
        return self._source

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_list

    def turn_off(self):
        """Turn off media player."""
        self.command(self._commands['power'] + '00')

    def set_volume_level(self, volume):
        """Set volume level, input is range 0..1. """
        self.command(self._commands['volume'] + format(int(volume*100), '02X'))

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        if mute:
            self.command(self._commands['mute'] + '01')
        else:
            self.command(self._commands['mute'] + '00')

    def turn_on(self):
        """Turn the media player on."""
        self.command(self._commands['power'] + '01')

    def select_source(self, source):
        """Set the input source."""
        sel = self._reverse_mapping.get(source.upper(), None)
        if not sel:
            for key,val in self._reverse_mapping.items():
                if source.upper() in key.split(','):
                    sel = self._reverse_mapping[key]

        if sel:
           self.command(self._commands['source'] + sel)
