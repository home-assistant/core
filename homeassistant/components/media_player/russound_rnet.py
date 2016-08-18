"""
Support for interfacing with Russound via RNET Protocol.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.russound_rnet/
"""
import logging

from homeassistant.components.media_player import (
    SUPPORT_TURN_OFF, SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET,
    SUPPORT_SELECT_SOURCE, MediaPlayerDevice)
from homeassistant.const import (
    CONF_HOST, CONF_PORT, STATE_OFF, STATE_ON)

REQUIREMENTS = [
    'https://github.com/laf/russound/archive/0.1.6.zip'
    '#russound==0.1.6']

ZONES = 'zones'
SOURCES = 'sources'

SUPPORT_RUSSOUND = SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_SET | \
                     SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Russound RNET platform."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)
    keypad = config.get('keypad', '70')

    if host is None or port is None:
        _LOGGER.error('Invalid config. Expected %s and %s',
                      CONF_HOST, CONF_PORT)
        return False

    from russound import russound

    russ = russound.Russound(host, port)
    russ.connect(keypad)

    sources = []
    for source in config[SOURCES]:
        sources.append(source['name'])

    if russ.is_connected():
        for zone_id, extra in config[ZONES].items():
            add_devices([RussoundRNETDevice(hass, russ, sources, zone_id,
                                            extra)])
    else:
        _LOGGER.error('Not connected to %s:%s', host, port)


# pylint: disable=abstract-method, too-many-public-methods,
# pylint: disable=too-many-instance-attributes, too-many-arguments
class RussoundRNETDevice(MediaPlayerDevice):
    """Representation of a Russound RNET device."""

    def __init__(self, hass, russ, sources, zone_id, extra):
        """Initialise the Russound RNET device."""
        self._name = extra['name']
        self._russ = russ
        self._state = STATE_OFF
        self._sources = sources
        self._zone_id = zone_id
        self._volume = 0

    @property
    def name(self):
        """Return the name of the zone."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def supported_media_commands(self):
        """Flag of media commands that are supported."""
        return SUPPORT_RUSSOUND

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self._volume = volume * 100
        self._russ.set_volume('1', self._zone_id, self._volume)

    def turn_on(self):
        """Turn the media player on."""
        self._russ.set_power('1', self._zone_id, '1')
        self._state = STATE_ON

    def turn_off(self):
        """Turn off media player."""
        self._russ.set_power('1', self._zone_id, '0')
        self._state = STATE_OFF

    def mute_volume(self, mute):
        """Send mute command."""
        self._russ.toggle_mute('1', self._zone_id)

    def select_source(self, source):
        """Set the input source."""
        if source in self._sources:
            index = self._sources.index(source)+1
            self._russ.set_source('1', self._zone_id, index)

    @property
    def source_list(self):
        """List of available input sources."""
        return self._sources
