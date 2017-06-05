"""
Support for Onkyo Receivers.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.onkyoserial/
"""
import logging
import voluptuous as vol

from homeassistant.components.media_player import (
    SUPPORT_TURN_OFF, SUPPORT_TURN_ON, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    SUPPORT_SELECT_SOURCE, SUPPORT_PLAY, MediaPlayerDevice, PLATFORM_SCHEMA)
from homeassistant.const import (STATE_OFF, STATE_ON, CONF_NAME)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = [
    'pyserial>=3.1.2',
    'https://github.com/rayzorben/onkyo-serial/archive/0.0.2.zip'
    '#onkyo_serial>=0.0.2'
]

_LOGGER = logging.getLogger(__name__)

SUPPORT_ONKYO = SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | \
    SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE | SUPPORT_PLAY

CONF_SOURCES = 'sources'
CONF_ZONES = 'zones'
CONF_PORT = 'port'

DEFAULT_NAME = 'Onkyo Serial Receiver'
DEFAULT_PORT = '/dev/ttyUSB0'

DEFAULT_ZONES = {
    'master': {
        'commands': {
            'power': 'PWR',
            'volume': 'MVL',
            'source': 'SLI',
            'mute': 'AMT'
            },
        'queries': {
            'power': 'PWRQSTN',
            'volume': 'MVLQSTN',
            'source': 'SLIQSTN',
            'mute': 'AMTQSTN'
            }
        },
    'zone2': {
        'commands': {
            'power': 'ZPW',
            'volume': 'ZVL',
            'source': 'SLZ',
            'mute': 'ZMT'
            },
        'queries': {
            'power': 'ZPWQSTN',
            'volume': 'ZVLQSTN',
            'source': 'SLZQSTN',
            'mute': 'ZMTQSTN'
        }
    }
}

ZONE_SETUP_SCHEMA = vol.Schema({
    vol.Required('commands'):
        vol.Schema({vol.All(cv.string): vol.Any(cv.string)}),
    vol.Required('queries'):
        vol.Schema({vol.All(cv.string): vol.Any(cv.string)})
})
ZONE_SCHEMA = vol.Schema({vol.All(cv.string): ZONE_SETUP_SCHEMA})

SOURCES_SCHEMA = vol.Schema({vol.All(cv.string): vol.Any(cv.string)})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PORT): cv.isdevice,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_ZONES): ZONE_SCHEMA,
    vol.Optional(CONF_SOURCES, SOURCES_SCHEMA):
        {cv.string: cv.string},
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Onkyo platform."""
    port = config.get(CONF_PORT)

    # merge the default zones overridden with the configuration.yaml
    # and create one device per zone
    zones = DEFAULT_ZONES
    if CONF_ZONES in config:
        zones = dict(zones.items() + config.get(CONF_ZONES))

    devices = list()
    for key in zones.keys():
        device = OnkyoSerialDevice(
            zones,
            key,
            port=port,
            sources=config.get(CONF_SOURCES),
            name="Onkyo-{zone}".format(zone=key)
        )
        devices.append(device)

    add_devices(devices, True)


class OnkyoSerialDevice(MediaPlayerDevice):
    """Representation of an Onkyo device."""

    def __init__(self, config, zone, port=None, sources=None, name=None):
        """Initialize the Onkyo Receiver."""
        from onkyo_serial import OnkyoSerial
        from onkyo_serial import ONKYO_SOURCES
        self._zone = zone
        self._mute = False
        self._volume = 0
        self._source = None
        self._power = STATE_OFF
        self._name = name
        self._sources = ONKYO_SOURCES
        if sources:
            self._sources = dict(self._sources.items() + sources.items())
        self._source_list = list(self._sources.values())
        # pylint: disable=E
        self._device = OnkyoSerial(config, zone, port=port)
        self._device.on_state_change += self.state_changed

    def state_changed(self, prop, value):
        """State has changed in the remote device, signalling an update."""
        if prop == 'power':
            self._power = STATE_ON if value else STATE_OFF

        if prop == 'volume':
            self._volume = value / 100

        if prop == 'source':
            self._source = value

        if prop == 'mute':
            self._mute = value

    def update(self):
        """Update request for status."""
        self._device.update()

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
        return self._mute

    @property
    def source(self):
        """"Return the current input source of the device."""
        return self._source

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_ONKYO

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_list

    def turn_on(self):
        """Turn the media player on."""
        self._device.power_on()

    def turn_off(self):
        """Turn off media player."""
        self._device.power_off()

    def set_volume_level(self, volume):
        """Set volume level, input is range 0..1."""
        self._device.volume(int(volume*100))

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        if mute:
            self._device.mute_on()
        else:
            self._device.mute_off()

    def select_source(self, source):
        """Set the input source."""
        self._device.source(source)
