"""
Support for interfacing with Monoprice 6 zone home audio controller.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.monoprice/
"""
import logging

import voluptuous as vol

from homeassistant.const import (CONF_NAME, CONF_PORT, STATE_OFF, STATE_ON)
import homeassistant.helpers.config_validation as cv
from homeassistant.components.media_player import (
    MediaPlayerDevice, PLATFORM_SCHEMA, SUPPORT_VOLUME_MUTE,
    SUPPORT_SELECT_SOURCE, SUPPORT_TURN_ON, SUPPORT_TURN_OFF,
    SUPPORT_VOLUME_SET, SUPPORT_VOLUME_STEP)


REQUIREMENTS = ['pymonoprice==0.2']

_LOGGER = logging.getLogger(__name__)

SUPPORT_MONOPRICE = SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_SET | \
                    SUPPORT_VOLUME_STEP | SUPPORT_TURN_ON | \
                    SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE

ZONE_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
})

SOURCE_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
})

CONF_ZONES = 'zones'
CONF_SOURCES = 'sources'

# Valid zone ids: 11-16 or 21-26 or 31-36
ZONE_IDS = vol.All(vol.Coerce(int), vol.Any(vol.Range(min=11, max=16),
                                            vol.Range(min=21, max=26),
                                            vol.Range(min=31, max=36)))

# Valid source ids: 1-6
SOURCE_IDS = vol.All(vol.Coerce(int), vol.Range(min=1, max=6))

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_PORT): cv.string,
    vol.Required(CONF_ZONES): vol.Schema({ZONE_IDS: ZONE_SCHEMA}),
    vol.Required(CONF_SOURCES): vol.Schema({SOURCE_IDS: SOURCE_SCHEMA}),
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Monoprice 6-zone amplifier platform."""
    port = config.get(CONF_PORT)

    from serial import SerialException
    from pymonoprice import Monoprice
    try:
        monoprice = Monoprice(port)
    except SerialException:
        _LOGGER.error('Error connecting to Monoprice controller.')
        return

    sources = {source_id: extra[CONF_NAME] for source_id, extra
               in config[CONF_SOURCES].items()}

    for zone_id, extra in config[CONF_ZONES].items():
        _LOGGER.info("Adding zone %d - %s", zone_id, extra[CONF_NAME])
        add_devices([MonopriceZone(monoprice, sources,
                                   zone_id, extra[CONF_NAME])], True)


class MonopriceZone(MediaPlayerDevice):
    """Representation of a a Monoprice amplifier zone."""

    # pylint: disable=too-many-public-methods

    def __init__(self, monoprice, sources, zone_id, zone_name):
        """Initialize new zone."""
        self._monoprice = monoprice
        # dict source_id -> source name
        self._source_id_name = sources
        # dict source name -> source_id
        self._source_name_id = {v: k for k, v in sources.items()}
        # ordered list of all source names
        self._source_names = sorted(self._source_name_id.keys(),
                                    key=lambda v: self._source_name_id[v])
        self._zone_id = zone_id
        self._name = zone_name

        self._state = None
        self._volume = None
        self._source = None
        self._mute = None

    def update(self):
        """Retrieve latest state."""
        state = self._monoprice.zone_status(self._zone_id)
        if not state:
            return False
        self._state = STATE_ON if state.power else STATE_OFF
        self._volume = state.volume
        self._mute = state.mute
        idx = state.source
        if idx in self._source_id_name:
            self._source = self._source_id_name[idx]
        else:
            self._source = None
        return True

    @property
    def name(self):
        """Return the name of the zone."""
        return self._name

    @property
    def state(self):
        """Return the state of the zone."""
        return self._state

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        if self._volume is None:
            return None
        return self._volume / 38.0

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._mute

    @property
    def supported_features(self):
        """Return flag of media commands that are supported."""
        return SUPPORT_MONOPRICE

    @property
    def source(self):
        """"Return the current input source of the device."""
        return self._source

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_names

    def select_source(self, source):
        """Set input source."""
        if source not in self._source_name_id:
            return
        idx = self._source_name_id[source]
        self._monoprice.set_source(self._zone_id, idx)

    def turn_on(self):
        """Turn the media player on."""
        self._monoprice.set_power(self._zone_id, True)

    def turn_off(self):
        """Turn the media player off."""
        self._monoprice.set_power(self._zone_id, False)

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        self._monoprice.set_mute(self._zone_id, mute)

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        self._monoprice.set_volume(self._zone_id, int(volume * 38))

    def volume_up(self):
        """Volume up the media player."""
        if self._volume is None:
            return
        self._monoprice.set_volume(self._zone_id,
                                   min(self._volume + 1, 38))

    def volume_down(self):
        """Volume down media player."""
        if self._volume is None:
            return
        self._monoprice.set_volume(self._zone_id,
                                   max(self._volume - 1, 0))
