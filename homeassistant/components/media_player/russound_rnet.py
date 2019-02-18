"""
Support for interfacing with Russound via RNET Protocol.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.russound_rnet/
"""
import logging

import voluptuous as vol

from homeassistant.components.media_player import (
    MediaPlayerDevice, PLATFORM_SCHEMA)
from homeassistant.components.media_player.const import (
    SUPPORT_SELECT_SOURCE, SUPPORT_TURN_OFF, SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE, SUPPORT_VOLUME_SET)
from homeassistant.const import (
    CONF_HOST, CONF_NAME, CONF_PORT, STATE_OFF, STATE_ON)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['russound==0.1.9']

_LOGGER = logging.getLogger(__name__)

CONF_ZONES = 'zones'
CONF_SOURCES = 'sources'

SUPPORT_RUSSOUND = SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_SET | \
                   SUPPORT_TURN_ON | SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE

ZONE_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
})

SOURCE_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_PORT): cv.port,
    vol.Required(CONF_ZONES): vol.Schema({cv.positive_int: ZONE_SCHEMA}),
    vol.Required(CONF_SOURCES): vol.All(cv.ensure_list, [SOURCE_SCHEMA]),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Russound RNET platform."""
    host = config.get(CONF_HOST)
    port = config.get(CONF_PORT)

    if host is None or port is None:
        _LOGGER.error("Invalid config. Expected %s and %s",
                      CONF_HOST, CONF_PORT)
        return False

    from russound import russound

    russ = russound.Russound(host, port)
    russ.connect()

    sources = []
    for source in config[CONF_SOURCES]:
        sources.append(source['name'])

    if russ.is_connected():
        for zone_id, extra in config[CONF_ZONES].items():
            add_entities([RussoundRNETDevice(
                hass, russ, sources, zone_id, extra)], True)
    else:
        _LOGGER.error('Not connected to %s:%s', host, port)


class RussoundRNETDevice(MediaPlayerDevice):
    """Representation of a Russound RNET device."""

    def __init__(self, hass, russ, sources, zone_id, extra):
        """Initialise the Russound RNET device."""
        self._name = extra['name']
        self._russ = russ
        self._sources = sources
        self._zone_id = zone_id

        self._state = None
        self._volume = None
        self._source = None

    def update(self):
        """Retrieve latest state."""
        # Updated this function to make a single call to get_zone_info, so that
        # with a single call we can get On/Off, Volume and Source, reducing the
        # amount of traffic and speeding up the update process.
        ret = self._russ.get_zone_info('1', self._zone_id, 4)
        _LOGGER.debug("ret= %s", ret)
        if ret is not None:
            _LOGGER.debug("Updating status for zone %s", self._zone_id)
            if ret[0] == 0:
                self._state = STATE_OFF
            else:
                self._state = STATE_ON
            self._volume = ret[2] * 2 / 100.0
        # Returns 0 based index for source.
            index = ret[1]
        # Possibility exists that user has defined list of all sources.
        # If a source is set externally that is beyond the defined list then
        # an exception will be thrown.
        # In this case return and unknown source (None)
            try:
                self._source = self._sources[index]
            except IndexError:
                self._source = None
        else:
            _LOGGER.error("Could not update status for zone %s", self._zone_id)

    @property
    def name(self):
        """Return the name of the zone."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_RUSSOUND

    @property
    def source(self):
        """Get the currently selected source."""
        return self._source

    @property
    def volume_level(self):
        """Volume level of the media player (0..1).

        Value is returned based on a range (0..100).
        Therefore float divide by 100 to get to the required range.
        """
        return self._volume

    def set_volume_level(self, volume):
        """Set volume level.  Volume has a range (0..1).

        Translate this to a range of (0..100) as expected
        by _russ.set_volume()
        """
        self._russ.set_volume('1', self._zone_id, volume * 100)

    def turn_on(self):
        """Turn the media player on."""
        self._russ.set_power('1', self._zone_id, '1')

    def turn_off(self):
        """Turn off media player."""
        self._russ.set_power('1', self._zone_id, '0')

    def mute_volume(self, mute):
        """Send mute command."""
        self._russ.toggle_mute('1', self._zone_id)

    def select_source(self, source):
        """Set the input source."""
        if source in self._sources:
            index = self._sources.index(source)
            # 0 based value for source
            self._russ.set_source('1', self._zone_id, index)

    @property
    def source_list(self):
        """Return a list of available input sources."""
        return self._sources
