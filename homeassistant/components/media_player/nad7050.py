"""
Support for NAD D 7050 digital amplifier.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/media_player.nad7050/
"""
import logging
import voluptuous as vol
from homeassistant.components.media_player import (
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_MUTE, SUPPORT_TURN_ON, SUPPORT_TURN_OFF,
    SUPPORT_VOLUME_STEP, SUPPORT_SELECT_SOURCE, MediaPlayerDevice,
    PLATFORM_SCHEMA)
from homeassistant.const import (
    CONF_NAME, STATE_OFF, STATE_ON)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['https://github.com/joopert/nad_receiver/archive/'
                '0.0.4.zip#nad_receiver==0.0.4']

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'NAD D 7050'
DEFAULT_MIN_VOLUME = -60
DEFAULT_MAX_VOLUME = -10
DEFAULT_VOLUME_STEP = 4

SUPPORT_NAD = SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | SUPPORT_TURN_ON | \
              SUPPORT_TURN_OFF | SUPPORT_VOLUME_STEP | SUPPORT_SELECT_SOURCE

CONF_MIN_VOLUME = 'min_volume'
CONF_MAX_VOLUME = 'max_volume'
CONF_VOLUME_STEP = 'volume_step'
CONF_HOST = 'host'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_MIN_VOLUME, default=DEFAULT_MIN_VOLUME): int,
    vol.Optional(CONF_MAX_VOLUME, default=DEFAULT_MAX_VOLUME): int,
    vol.Optional(CONF_VOLUME_STEP, default=DEFAULT_VOLUME_STEP): int,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the NAD platform."""
    from nad_receiver import NADReceiverTCP
    add_devices([NAD7050(
        NADReceiverTCP(config.get(CONF_HOST)),
        config.get(CONF_NAME),
        config.get(CONF_MIN_VOLUME),
        config.get(CONF_MAX_VOLUME),
        config.get(CONF_VOLUME_STEP),
    )])


class NAD7050(MediaPlayerDevice):
    """Representation of a NAD D 7050 device."""

    def __init__(self, d7050, name, min_volume, max_volume, volume_step):
        """Initialize the amplifier."""
        self._name = name
        self.d7050 = d7050
        self._min_vol = (min_volume + 90) * 2  # from dB to nad vol (0-200)
        self._max_vol = (max_volume + 90) * 2  # from dB to nad vol (0-200)
        self._volume_step = volume_step
        self._state = None
        self._mute = None
        self._nad_volume = None
        self._volume = None
        self._source = None
        self._source_list = d7050.available_sources()

        self.update()

    @property
    def name(self):
        """Return the name of the device."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    def update(self):
        """Get the latest details from the device."""
        nad_status = self.d7050.status()

        if nad_status is None:
            return

        # Update on/off state
        if nad_status['power']:
            self._state = STATE_ON
        else:
            self._state = STATE_OFF

        # Update current volume
        self._volume = self.nad_vol_to_internal_vol(nad_status['volume'])
        self._nad_volume = nad_status['volume']

        # Update muted state
        self._mute = nad_status['muted']

        # Update current source
        self._source = nad_status['source']

    def nad_vol_to_internal_vol(self, nad_volume):
        """Convert nad volume range (0-200) to internal volume range.

        Takes into account configured min and max volume.
        """
        if nad_volume < self._min_vol:
            volume_internal = 0.0
        if nad_volume > self._max_vol:
            volume_internal = 1.0
        else:
            volume_internal = (nad_volume - self._min_vol) / \
                              (self._max_vol - self._min_vol)
        return volume_internal

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return SUPPORT_NAD

    def turn_off(self):
        """Turn the media player off."""
        self.d7050.power_off()

    def turn_on(self):
        """Turn the media player on."""
        self.d7050.power_on()

    def volume_up(self):
        """Step volume up in the configured increments."""
        self.d7050.set_volume(self._nad_volume + 2 * self._volume_step)

    def volume_down(self):
        """Step volume down in the configured increments."""
        self.d7050.set_volume(self._nad_volume - 2 * self._volume_step)

    def set_volume_level(self, volume):
        """Set volume level, range 0..1."""
        nad_volume_to_set = \
            int(round(volume * (self._max_vol - self._min_vol) +
                      self._min_vol))
        self.d7050.set_volume(nad_volume_to_set)

    def mute_volume(self, mute):
        """Mute (true) or unmute (false) media player."""
        if mute:
            self.d7050.mute()
        else:
            self.d7050.unmute()

    def select_source(self, source):
        """Select input source."""
        self.d7050.select_source(source)

    @property
    def source(self):
        """Name of the current input source."""
        return self._source

    @property
    def source_list(self):
        """List of available input sources."""
        return self.d7050.available_sources()

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        return self._volume

    @property
    def is_volume_muted(self):
        """Boolean if volume is currently muted."""
        return self._mute
